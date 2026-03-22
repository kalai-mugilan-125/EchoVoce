"""
services/tts_service.py
───────────────────────
Text-to-Speech using Piper TTS (ONNX, CPU-native).

• Converts text → WAV audio bytes
• Piper is extremely fast on CPU (~150ms for a sentence)
• Returns raw WAV bytes that are sent over WebSocket to the browser
• Supports streaming: synthesise sentence-by-sentence for low latency
"""

import io
import wave
import subprocess
import tempfile
import os
from pathlib import Path
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class TTSService:
    """
    Piper TTS wrapper.

    Piper is invoked as a subprocess (most reliable cross-platform approach).
    It reads text from stdin and writes WAV to stdout.

    Alternative: use piper-tts Python bindings if installed.
    """

    def __init__(self):
        self._model_path = settings.TTS_MODEL_PATH
        self._config_path = settings.TTS_CONFIG_PATH
        self._is_ready = False
        self._use_python_api = False

    def load(self):
        """Verify model files exist and choose invocation method."""
        if self._is_ready:
            return

        model_ok = Path(self._model_path).exists()
        config_ok = Path(self._config_path).exists()

        if not model_ok or not config_ok:
            logger.warning(
                f"Piper model files missing: onnx={model_ok} json={config_ok}. "
                "Run download_models.py first."
            )
            self._is_ready = False
            return

        # Try Python API first
        try:
            from piper import PiperVoice
            self._voice = PiperVoice.load(self._model_path, config_path=self._config_path)
            self._use_python_api = True
            logger.info("TTS loaded via piper Python API")
        except ImportError:
            logger.info("piper Python API not found — falling back to subprocess mode")
            self._use_python_api = False

        self._is_ready = True
        logger.info(f"TTS ready: {Path(self._model_path).name}")

    def synthesise(self, text: str) -> bytes:
        """
        Convert text → WAV audio bytes.

        Args:
            text: Plain text sentence (no markdown, no SSML)

        Returns:
            Raw WAV bytes (16-bit PCM, 22050 Hz mono)
        """
        if not self._is_ready:
            self.load()

        if not text.strip():
            return b""

        # Clean text — remove any stray markdown characters
        clean = text.replace("*", "").replace("#", "").replace("`", "").strip()

        if self._use_python_api:
            return self._synth_python(clean)
        return self._synth_subprocess(clean)

    def _synth_python(self, text: str) -> bytes:
        """Synthesise using piper Python bindings (faster, in-process)."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            self._voice.synthesize(text, wav)
        return buf.getvalue()

    def _synth_subprocess(self, text: str) -> bytes:
        """
        Synthesise by calling piper CLI as subprocess.
        Fallback when Python API is unavailable.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [
                    "piper",
                    "--model", self._model_path,
                    "--config", self._config_path,
                    "--output_file", tmp_path,
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"Piper subprocess error: {result.stderr.decode()}")
                return b""

            with open(tmp_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.error("piper binary not found. Install with: pip install piper-tts")
            return b""
        except subprocess.TimeoutExpired:
            logger.error("Piper TTS timed out")
            return b""
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def synthesise_stream(self, sentences: list[str]) -> list[bytes]:
        """
        Synthesise a list of sentences, returning a list of WAV byte chunks.
        Each chunk can be sent over WebSocket immediately after synthesis,
        enabling streaming playback on the frontend.
        """
        chunks = []
        for sentence in sentences:
            wav_bytes = self.synthesise(sentence)
            if wav_bytes:
                chunks.append(wav_bytes)
        return chunks

    def get_silence_wav(self, duration_ms: int = 200) -> bytes:
        """
        Generate a short silent WAV chunk.
        Used for padding between sentences during streaming.
        """
        sample_rate = 22050
        num_samples = int(sample_rate * duration_ms / 1000)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * num_samples)
        return buf.getvalue()


# Singleton
tts_service = TTSService()
