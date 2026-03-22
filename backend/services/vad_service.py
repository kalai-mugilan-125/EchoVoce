"""
services/vad_service.py
───────────────────────
Voice Activity Detection using Silero VAD.

Responsibilities:
  • Detect speech vs silence in incoming audio chunks
  • Track cumulative silence duration
  • Fire a silence_callback when silence exceeds VAD_SILENCE_THRESHOLD (5s)
  • Fire an interrupt_callback when speech is detected while AI is talking

Works fully on CPU — Silero VAD is a tiny LSTM model (~1 MB).
"""

import time
import numpy as np
import torch
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class VADService:
    def __init__(self):
        self._model = None
        self._get_speech_ts = None
        self._silence_start: float | None = None
        self._is_loaded = False

    def load(self):
        """Load Silero VAD model. Called once at startup."""
        if self._is_loaded:
            return
        logger.info("Loading Silero VAD model...")
        try:
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._model = model
            # get_speech_timestamps is available but we use per-chunk inference
            self._is_loaded = True
            logger.info("VAD model loaded (CPU)")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD: {e}")
            raise

    def _audio_to_tensor(self, audio_bytes: bytes) -> torch.Tensor:
        """Convert raw PCM int16 bytes → float32 tensor normalised to [-1, 1]."""
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_np /= 32768.0
        return torch.from_tensor(audio_np) if hasattr(torch, "from_tensor") \
            else torch.tensor(audio_np)

    def is_speech(self, audio_bytes: bytes) -> tuple[bool, float]:
        """
        Run VAD on a single audio chunk.

        Returns:
            (is_speech: bool, confidence: float 0.0–1.0)
        """
        if not self._is_loaded:
            self.load()

        tensor = self._audio_to_tensor(audio_bytes)

        # Silero expects chunks of exactly 512 samples at 16kHz
        if len(tensor) < settings.VAD_CHUNK_SIZE:
            tensor = torch.nn.functional.pad(
                tensor, (0, settings.VAD_CHUNK_SIZE - len(tensor))
            )
        tensor = tensor[: settings.VAD_CHUNK_SIZE]

        with torch.no_grad():
            confidence = self._model(tensor, settings.VAD_SAMPLE_RATE).item()

        speech_detected = confidence >= settings.VAD_SPEECH_THRESHOLD
        return speech_detected, confidence

    def process_chunk(
        self,
        audio_bytes: bytes,
        ai_is_speaking: bool = False,
    ) -> dict:
        """
        Process one audio chunk and return a status dict.

        Returns dict with keys:
          • speech_detected (bool)
          • confidence (float)
          • silence_duration (float) — seconds of continuous silence
          • should_stop_input (bool) — True after 5s silence
          • interrupt_ai (bool) — True if user spoke while AI was talking
        """
        speech, confidence = self.is_speech(audio_bytes)

        interrupt_ai = False
        if speech and ai_is_speaking:
            interrupt_ai = True
            logger.info("Interrupt detected — user spoke while AI was talking")

        # Track silence window
        should_stop = False
        silence_duration = 0.0

        if speech:
            self._silence_start = None  # reset silence timer
        else:
            if self._silence_start is None:
                self._silence_start = time.monotonic()
            silence_duration = time.monotonic() - self._silence_start
            if silence_duration >= settings.VAD_SILENCE_THRESHOLD:
                should_stop = True
                self._silence_start = None  # reset after firing

        return {
            "speech_detected": speech,
            "confidence": round(confidence, 3),
            "silence_duration": round(silence_duration, 2),
            "should_stop_input": should_stop,
            "interrupt_ai": interrupt_ai,
        }

    def reset(self):
        """Reset silence tracking — call at start of each user turn."""
        self._silence_start = None


# Singleton
vad_service = VADService()
