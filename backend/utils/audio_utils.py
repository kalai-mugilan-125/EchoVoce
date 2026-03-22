"""
utils/audio_utils.py
────────────────────
Audio format helpers used across the pipeline.

Browser → Backend: raw PCM int16 at 16kHz (via WebSocket binary frames)
Backend → Browser: WAV bytes (16-bit PCM, 22050 Hz from Piper)
"""

import io
import wave
import numpy as np
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────
INPUT_SAMPLE_RATE = 16000   # Browser mic recording rate
OUTPUT_SAMPLE_RATE = 22050  # Piper TTS output rate
CHANNELS = 1                # Mono
SAMPLE_WIDTH = 2            # 16-bit = 2 bytes


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = INPUT_SAMPLE_RATE) -> bytes:
    """
    Wrap raw PCM int16 bytes in a WAV header.
    Needed when passing audio to libraries that expect WAV format.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buf.getvalue()


def wav_to_pcm(wav_bytes: bytes) -> bytes:
    """Extract raw PCM frames from a WAV file."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wav:
        return wav.readframes(wav.getnframes())


def pcm_bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert raw int16 PCM bytes → float32 numpy array [-1.0, 1.0]."""
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    audio /= 32768.0
    return audio


def float32_to_pcm_bytes(audio: np.ndarray) -> bytes:
    """Convert float32 numpy array → int16 PCM bytes."""
    audio_clipped = np.clip(audio, -1.0, 1.0)
    return (audio_clipped * 32768).astype(np.int16).tobytes()


def resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Simple linear resampling.
    For high-quality resampling install librosa and use librosa.resample().
    """
    if orig_sr == target_sr:
        return audio
    try:
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
    except ImportError:
        # Fallback: crude integer resampling
        ratio = target_sr / orig_sr
        new_len = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, new_len)
        return np.interp(indices, np.arange(len(audio)), audio)


def split_audio_chunks(audio_bytes: bytes, chunk_size: int = 1024) -> list[bytes]:
    """
    Split a large audio bytes buffer into fixed-size chunks.
    Used to feed audio incrementally to VAD.
    """
    chunks = []
    for i in range(0, len(audio_bytes), chunk_size):
        chunks.append(audio_bytes[i: i + chunk_size])
    return chunks


def compute_rms(audio_bytes: bytes) -> float:
    """
    Compute RMS energy of audio chunk.
    Useful for simple silence detection as a VAD fallback.
    """
    audio = pcm_bytes_to_float32(audio_bytes)
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio ** 2)))


def is_silent_rms(audio_bytes: bytes, threshold: float = 0.01) -> bool:
    """Simple RMS-based silence check (fallback when VAD model unavailable)."""
    return compute_rms(audio_bytes) < threshold
