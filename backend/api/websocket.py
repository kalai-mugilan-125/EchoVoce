"""
api/websocket.py
────────────────
Real-time WebSocket endpoint.

Fix: greeting is now triggered by injecting a synthetic first user message
directly into the LLM — no audio needed for the first turn.
"""

import asyncio
import json
import re
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


async def _stream_tts(ws: WebSocket, session: InterviewSession, text: str):
    """Split text into sentences, synthesise each one, stream WAV to client."""
    session.is_ai_speaking = True
    loop = asyncio.get_event_loop()

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        sentences = [text.strip()]

    for sentence in sentences:
        if session.interrupt_requested:
            logger.info(f"[{session.session_id[:8]}] TTS interrupted")
            session.clear_interrupt()
            await _send_json(ws, {"type": "interrupt_ack"})
            session.is_ai_speaking = False
            return

        await _send_json(ws, {"type": "tts_start", "sentence": sentence})
        wav = await loop.run_in_executor(None, tts_service.synthesise, sentence)
        if wav:
            await _send_bytes(ws, wav)
        await _send_json(ws, {"type": "tts_end"})
        await asyncio.sleep(0.05)

    session.is_ai_speaking = False
    await _send_json(ws, {"type": "listening"})


async def _run_pipeline(ws: WebSocket, session: InterviewSession, user_text: str):
    """
    user_text → LLM → TTS → WebSocket.
    Acquires a per-session async lock so only one pipeline runs at a time.
    This prevents the OSError access violation from concurrent llama-cpp calls.
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

        logger.info(f"[{session.session_id[:8]}] LLM: '{user_text[:80]}'")

        response = await loop.run_in_executor(
            None,
            lambda: llm_service.generate(messages, stream=False)
        )
        response = (response or "").strip()

        if not response:
            logger.warning(f"[{session.session_id[:8]}] Empty LLM response")
            await _send_json(ws, {"type": "listening"})
            return

        logger.info(f"[{session.session_id[:8]}] Response: '{response[:80]}'")
        session.add_message("assistant", response)
        session.question_count += 1

        await _stream_tts(ws, session, response)


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
    await _run_pipeline(ws, session, transcript)


@router.websocket("/ws/interview")
async def websocket_interview(websocket: WebSocket):
    await websocket.accept()
    session: InterviewSession | None = None
    logger.info("WebSocket connected")

    try:
        while True:
            message = await websocket.receive()

            # ── Binary: audio chunk ──────────────────────────
            if message.get("bytes"):
                audio_chunk = message["bytes"]

                # Ignore audio while AI is speaking
                if session is None or session.is_ai_speaking:
                    continue

                buf = _audio_buffers.setdefault(session.session_id, bytearray())
                buf.extend(audio_chunk)

                vad_result = vad_service.process_chunk(
                    bytes(audio_chunk),
                    ai_is_speaking=session.is_ai_speaking,
                )

                if vad_result["interrupt_ai"]:
                    session.request_interrupt()

                if vad_result["should_stop_input"]:
                    accumulated = bytes(buf)
                    _audio_buffers[session.session_id] = bytearray()
                    vad_service.reset()

                    if len(accumulated) > 3200:
                        asyncio.create_task(
                            _process_audio(websocket, session, accumulated)
                        )
                    else:
                        await _send_json(websocket, {"type": "listening"})

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
                        f"resume={'yes' if session.resume_text else 'no'} | "
                        f"jd={'yes' if session.job_description else 'no'}"
                    )

                    # Trigger greeting — inject synthetic first message
                    if session.has_context():
                        trigger = (
                            "Please greet the candidate warmly by name if available, "
                            "then ask your first interview question based on their resume "
                            "and the job description."
                        )
                    else:
                        trigger = (
                            "Please greet the candidate warmly and ask your first "
                            "general interview question."
                        )

                    asyncio.create_task(_run_pipeline(websocket, session, trigger))

                elif msg_type == "end":
                    if session:
                        logger.info(f"[{session.session_id[:8]}] Ended by client")
                        session_manager.delete(session.session_id)
                        _audio_buffers.pop(session.session_id, None)
                    break

                elif msg_type == "interrupt":
                    if session:
                        session.request_interrupt()

                elif msg_type == "ping":
                    await _send_json(websocket, {"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WS disconnected: {session.session_id[:8] if session else '?'}")
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
