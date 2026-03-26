"""
api/websocket.py
────────────────
Real-time WebSocket endpoint.

Fix: greeting is now triggered by injecting a synthetic first user message
directly into the LLM — no audio needed for the first turn.
"""

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from core.session_manager import session_manager, InterviewSession
from core.prompt_builder import build_system_prompt
from services.vad_service import vad_service
from services.stt_service import stt_service
from services.llm_service import llm_service
from services.tts_service import tts_service
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

_audio_buffers: dict[str, bytearray] = {}
_processing_locks: dict[str, asyncio.Lock] = {}  # prevents concurrent LLM calls per session


async def _send_json(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except Exception:
        pass


async def _send_bytes(ws: WebSocket, data: bytes):
    try:
        await ws.send_bytes(data)
    except Exception:
        pass


async def _synthesise_and_send(ws: WebSocket, session: InterviewSession, sentence: str) -> bool:
    """
    Synthesise a single sentence with TTS and send the WAV over WebSocket.
    Returns False if interrupted, True otherwise.
    """
    if session.interrupt_requested:
        logger.info(f"[{session.session_id[:8]}] TTS interrupted")
        session.clear_interrupt()
        await _send_json(ws, {"type": "interrupt_ack"})
        session.is_ai_speaking = False
        return False

    loop = asyncio.get_event_loop()
    await _send_json(ws, {"type": "tts_start", "sentence": sentence})
    wav = await loop.run_in_executor(None, tts_service.synthesise, sentence)
    if wav:
        await _send_bytes(ws, wav)
    await _send_json(ws, {"type": "tts_end"})
    await asyncio.sleep(0.05)
    return True


async def _run_pipeline(ws: WebSocket, session: InterviewSession, user_text: str):
    """
    user_text → LLM (streaming sentences) → TTS → WebSocket.

    Each sentence is synthesised with Piper TTS as soon as the LLM yields it,
    so audio playback starts after the first sentence — no need to wait for
    the full LLM response.

    Acquires a per-session async lock so only one pipeline runs at a time.
    """
    lock = _processing_locks.setdefault(session.session_id, asyncio.Lock())

    # If already processing, drop this turn — avoids queue buildup
    if lock.locked():
        logger.info(f"[{session.session_id[:8]}] Pipeline busy — dropping turn")
        return

    async with lock:
        loop = asyncio.get_event_loop()

        if user_text:
            session.add_message("user", user_text)
        messages = session.get_history_dicts()

        logger.info(f"[{session.session_id[:8]}] LLM streaming: '{user_text[:80]}'")
        session.is_ai_speaking = True

        full_response_parts: list[str] = []

        # Run the blocking sentence generator in a thread and consume it
        # asynchronously so the event loop stays responsive.
        sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _produce_sentences():
            """Runs in a thread pool — feeds sentences into the async queue safely."""
            try:
                for sentence in llm_service.generate_stream_sentences(messages):
                    loop.call_soon_threadsafe(sentence_queue.put_nowait, sentence)
            except Exception as exc:
                logger.error(f"LLM stream error in producer: {exc}")
            finally:
                loop.call_soon_threadsafe(sentence_queue.put_nowait, None)  # sentinel

        producer = loop.run_in_executor(None, _produce_sentences)

        interrupted = False
        while True:
            sentence = await sentence_queue.get()
            if sentence is None:  # LLM finished
                break

            sentence = sentence.strip()
            if not sentence:
                continue

            full_response_parts.append(sentence)
            logger.info(f"[{session.session_id[:8]}] TTS sentence: '{sentence[:60]}'")

            ok = await _synthesise_and_send(ws, session, sentence)
            if not ok:
                interrupted = True
                break

        # Make sure the producer thread is done before releasing the lock
        await producer

        full_response = " ".join(full_response_parts).strip()
        if full_response:
            session.add_message("assistant", full_response)
            session.question_count += 1
            logger.info(f"[{session.session_id[:8]}] Full response: '{full_response[:80]}'")
        else:
            logger.warning(f"[{session.session_id[:8]}] Empty LLM response")

        if not interrupted:
            logger.info(f"[{session.session_id[:8]}] LLM generation complete. Waiting for TTS playback to finish.")


async def _process_audio_streaming(ws: WebSocket, session: InterviewSession, audio_bytes: bytes):
    """
    Word-by-word streaming STT. Runs continuously in background thread
    every 0.5s of new audio to provide real-time frontend feedback.
    """
    loop = asyncio.get_event_loop()
    
    # transcribe_streaming expects float32 numpy array
    import numpy as np
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
    audio_np /= 32768.0

    text = await loop.run_in_executor(
        None,
        lambda: stt_service.transcribe_streaming(audio_np)
    )
    
    if text:
        await _send_json(ws, {"type": "transcript_partial", "text": text})
    
    # Release streaming lock for this session
    setattr(session, "is_streaming_stt", False)


async def _process_audio(ws: WebSocket, session: InterviewSession, audio_bytes: bytes):
    """STT on accumulated audio → pipeline."""
    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(
        None,
        lambda: stt_service.transcribe(audio_bytes, is_wav=False)
    )
    transcript = (result.get("text") or "").strip()

    if not transcript:
        logger.info(f"[{session.session_id[:8]}] Empty STT — re-listening")
        await _send_json(ws, {"type": "listening"})
        return

    logger.info(f"[{session.session_id[:8]}] STT: '{transcript}'")
    await _send_json(ws, {"type": "transcript", "text": transcript})
    
    # Reset streaming state for the next turn
    setattr(session, "last_streaming_len", 0)
    setattr(session, "is_streaming_stt", False)
    
    await _run_pipeline(ws, session, transcript)


@router.websocket("/ws/interview")
async def websocket_interview(websocket: WebSocket):
    await websocket.accept()
    session: InterviewSession | None = None
    logger.info("WebSocket connected")

    try:
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            # ── Binary: audio chunk ──────────────────────────
            if message.get("bytes"):
                audio_chunk = message["bytes"]

                # Ignore audio while AI is speaking
                if session is None or session.is_ai_speaking:
                    logger.debug(f"Audio chunk dropped: session={session}, ai_speaking={session.is_ai_speaking if session else 'None'}")
                    continue

                if len(audio_chunk) > 0:
                    logger.info(f"Received audio chunk size: {len(audio_chunk)}")

                buf = _audio_buffers.setdefault(session.session_id, bytearray())
                buf.extend(audio_chunk)

                vad_result = vad_service.process_chunk(
                    bytes(audio_chunk),
                    ai_is_speaking=session.is_ai_speaking,
                )

                if vad_result["interrupt_ai"]:
                    session.request_interrupt()

                # ── No auto-stop: silence is now user-controlled via Answer button ──
                # Only run streaming partial STT for live preview.
                last_len = getattr(session, "last_streaming_len", 0)
                if len(buf) - last_len >= 16000:
                    if not getattr(session, "is_streaming_stt", False):
                        setattr(session, "last_streaming_len", len(buf))
                        setattr(session, "is_streaming_stt", True)
                        asyncio.create_task(_process_audio_streaming(websocket, session, bytes(buf)))

            # ── Text: JSON control ───────────────────────────
            elif message.get("text"):
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "start":
                    sid   = data.get("session_id")
                    style = data.get("style", "mixed")

                    if sid:
                        session = session_manager.get(sid)
                    if session is None:
                        session = session_manager.create()

                    _audio_buffers[session.session_id] = bytearray()
                    setattr(session, "last_streaming_len", 0)
                    setattr(session, "is_streaming_stt", False)
                    vad_service.reset()

                    # Seed system prompt
                    system_prompt = build_system_prompt(session, style=style)
                    session.history.clear()
                    session.add_message("system", system_prompt)

                    await _send_json(websocket, {
                        "type": "ready",
                        "session_id": session.session_id,
                    })

                    logger.info(
                        f"[{session.session_id[:8]}] Started | style={style} | "
                        f"resume={'yes (' + str(len(session.resume_text)) + ' chars)' if session.resume_text else 'no'} | "
                        f"jd={'yes (' + str(len(session.job_description)) + ' chars)' if session.job_description else 'no'}"
                    )

                    # Trigger greeting — inject synthetic first message
                    trigger = "Hello, I am ready to start the interview."

                    asyncio.create_task(_run_pipeline(websocket, session, trigger))

                elif msg_type == "end":
                    if session:
                        logger.info(f"[{session.session_id[:8]}] Ended by client")
                        session_manager.delete(session.session_id)
                        _audio_buffers.pop(session.session_id, None)
                    break

                elif msg_type == "submit_answer":
                    logger.info("Received message: submit_answer")
                    # User clicked the Answer button — run final STT on everything recorded so far
                    if session:
                        buf = _audio_buffers.get(session.session_id, bytearray())
                        accumulated = bytes(buf)
                        _audio_buffers[session.session_id] = bytearray()
                        setattr(session, "last_streaming_len", 0)
                        setattr(session, "is_streaming_stt", False)
                        vad_service.reset()

                        if len(accumulated) > 3200:
                            logger.info(f"[{session.session_id[:8]}] Answer submitted — {len(accumulated)} bytes to STT")
                            asyncio.create_task(
                                _process_audio(websocket, session, accumulated)
                            )
                        else:
                            logger.info(f"[{session.session_id[:8]}] Answer submitted but buffer too small — re-listening")
                            await _send_json(websocket, {"type": "listening"})

                elif msg_type == "interrupt":
                    if session:
                        session.request_interrupt()

                elif msg_type == "tts_playback_done":
                    if session:
                        session.is_ai_speaking = False
                        await _send_json(websocket, {"type": "listening"})
                        logger.info(f"[{session.session_id[:8]}] TTS playback done. Listening...")

                elif msg_type == "ping":
                    await _send_json(websocket, {"type": "pong"})

    except (WebSocketDisconnect, RuntimeError) as e:
        # RuntimeError fires when receive() is called after the client already
        # sent a disconnect frame — treat it the same as a clean disconnect.
        msg = str(e)
        if "disconnect" in msg.lower() or isinstance(e, WebSocketDisconnect):
            logger.info(f"WS disconnected: {session.session_id[:8] if session else '?'}")
        else:
            logger.error(f"WS runtime error: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"WS error: {e}", exc_info=True)
        await _send_json(websocket, {"type": "error", "message": str(e)})
    finally:
        if session:
            session_manager.delete(session.session_id)
            _audio_buffers.pop(session.session_id, None)
            _processing_locks.pop(session.session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass
