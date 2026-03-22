"""
services/stt_service.py
───────────────────────
Speech-to-Text using faster-whisper (CTranslate2 backend).

• Runs on CPU with int8 quantisation — fast even without GPU
• Accepts raw PCM bytes or WAV bytes
• Returns transcript text + detected language + word-level segments
• Model is loaded once at startup and reused across all sessions
"""

import io
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class STTService:
    def __init__(self):
        self._model: WhisperModel | None = None
        self._is_loaded = False

    def load(self):
        """Load faster-whisper model. Called once at app startup."""
        if self._is_loaded:
            return
        logger.info(
            f"Loading Whisper model: size={settings.WHISPER_MODEL_SIZE} "
            f"device={settings.WHISPER_DEVICE} compute={settings.WHISPER_COMPUTE_TYPE}"
        )
        self._model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
            download_root=settings.WHISPER_MODEL_PATH,
        )
        self._is_loaded = True
        logger.info("Whisper STT model ready")

    def _bytes_to_float32(self, audio_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
        """
        Convert raw PCM int16 bytes → float32 numpy array at 16kHz.
        faster-whisper expects float32 audio at 16kHz mono.
        """
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_np /= 32768.0
        return audio_np

    def _wav_to_float32(self, wav_bytes: bytes) -> tuple[np.ndarray, int]:
        """Read WAV file bytes → float32 array + sample rate."""
        buf = io.BytesIO(wav_bytes)
        audio_np, sr = sf.read(buf, dtype="float32")
        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)  # stereo → mono
        return audio_np, sr

    def transcribe(
        self,
        audio_bytes: bytes,
        is_wav: bool = False,
        language: str = "en",
    ) -> dict:
        """
        Transcribe audio bytes → text.

        Args:
            audio_bytes: Raw PCM int16 bytes OR WAV file bytes
            is_wav:      Set True if input is a WAV file
            language:    Language hint (default "en")

        Returns dict with:
            text (str), language (str), confidence (float), segments (list)
        """
        if not self._is_loaded:
            self.load()

        if is_wav:
            audio_np, _ = self._wav_to_float32(audio_bytes)
        else:
            audio_np = self._bytes_to_float32(audio_bytes)

        # Whisper needs at least 0.1s of audio
        if len(audio_np) < 1600:
            return {"text": "", "language": language, "confidence": 0.0, "segments": []}

        segments_iter, info = self._model.transcribe(
            audio_np,
            language=language,
            beam_size=3,          # reduced beam for faster CPU inference
            vad_filter=True,      # built-in VAD to skip silence
            vad_parameters={"min_silence_duration_ms": 300},
        )

        segments = []
        full_text_parts = []

        for seg in segments_iter:
            segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts).strip()
        logger.info(f"STT transcript: '{full_text}' (lang={info.language})")

        return {
            "text": full_text,
            "language": info.language,
            "confidence": round(info.language_probability, 3),
            "segments": segments,
        }

    def transcribe_streaming(self, audio_np: np.ndarray) -> str:
        """
        Lightweight transcription for streaming use.
        Returns only the text string (no metadata).
        """
        if not self._is_loaded:
            self.load()

        if len(audio_np) < 1600:
            return ""

        segments_iter, _ = self._model.transcribe(
            audio_np,
            language="en",
            beam_size=1,   # fastest possible for real-time
            vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments_iter).strip()


# Singleton
stt_service = STTService()
