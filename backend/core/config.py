"""
core/config.py
──────────────
Central settings loaded from .env.
All services import `settings` from here — single source of truth.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):

    # ── Device ────────────────────────────────────────────
    DEVICE: str = "cpu"  # "cpu" | "cuda"

    # ── LLM ───────────────────────────────────────────────
    LLM_MODEL_PATH: str = "models/llm/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    LLM_N_CTX: int = 4096
    LLM_MAX_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.7
    LLM_N_THREADS: int = 4
    LLM_N_GPU_LAYERS: int = 0  # 0 = CPU only

    # ── STT ───────────────────────────────────────────────
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_MODEL_PATH: str = "models/whisper"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # ── TTS ───────────────────────────────────────────────
    TTS_MODEL_PATH: str = "models/tts/en_US-lessac-medium.onnx"
    TTS_CONFIG_PATH: str = "models/tts/en_US-lessac-medium.onnx.json"
    TTS_ENGINE: str = "piper"

    # ── VAD ───────────────────────────────────────────────
    VAD_SILENCE_THRESHOLD: float = 5.0
    VAD_SPEECH_THRESHOLD: float = 0.5
    VAD_SAMPLE_RATE: int = 16000
    VAD_CHUNK_SIZE: int = 512

    # ── Server ────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = False

    # ── Upload ────────────────────────────────────────────
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10

    # ── Logging ───────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    @field_validator("DEVICE")
    @classmethod
    def validate_device(cls, v: str) -> str:
        if v not in ("cpu", "cuda"):
            raise ValueError("DEVICE must be 'cpu' or 'cuda'")
        return v

    @property
    def is_gpu(self) -> bool:
        return self.DEVICE == "cuda"

    @property
    def llm_model_abs(self) -> Path:
        return Path(self.LLM_MODEL_PATH).resolve()

    @property
    def whisper_model_abs(self) -> Path:
        return Path(self.WHISPER_MODEL_PATH).resolve()

    @property
    def tts_model_abs(self) -> Path:
        return Path(self.TTS_MODEL_PATH).resolve()

    @property
    def upload_dir_abs(self) -> Path:
        p = Path(self.UPLOAD_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
