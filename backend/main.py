"""
main.py
───────
FastAPI application entry point.

Startup sequence:
  1. Load VAD model   (Silero — ~1 MB, loads in <1s)
  2. Load Whisper STT (faster-whisper small — loads in ~3–5s on CPU)
  3. Load Piper TTS   (ONNX — loads in ~1s)
  4. Load LLM         (GGUF — loads in ~10–30s on CPU, varies by model size)

All models are loaded ONCE at startup and reused across all sessions.
The WebSocket server is ready only after all models are loaded.

Run:
    uvicorn main:app --host 0.0.0.0 --port 8000
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from services.vad_service import vad_service
from services.stt_service import stt_service
from services.tts_service import tts_service
from services.llm_service import llm_service
from api.websocket import router as ws_router
from api.upload import router as upload_router
from api.health import router as health_router
from utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Load all AI models on startup.
    Models are loaded in a thread pool to avoid blocking the event loop.
    """
    logger.info("=" * 50)
    logger.info("AI Interviewer Backend — Starting Up")
    logger.info(f"Device: {settings.DEVICE.upper()}")
    logger.info(f"LLM: {settings.LLM_MODEL_PATH}")
    logger.info(f"Whisper: {settings.WHISPER_MODEL_SIZE}")
    logger.info("=" * 50)

    loop = asyncio.get_event_loop()

    # Load VAD (fast — ~1s)
    logger.info("[1/4] Loading VAD model...")
    try:
        await loop.run_in_executor(None, vad_service.load)
        logger.info("[1/4] VAD ready")
    except Exception as e:
        logger.error(f"[1/4] VAD load failed: {e}")

    # Load Whisper STT (~3–5s on CPU)
    logger.info("[2/4] Loading Whisper STT model...")
    try:
        await loop.run_in_executor(None, stt_service.load)
        logger.info("[2/4] Whisper STT ready")
    except Exception as e:
        logger.error(f"[2/4] Whisper load failed: {e}")

    # Load Piper TTS (~1s)
    logger.info("[3/4] Loading Piper TTS model...")
    try:
        await loop.run_in_executor(None, tts_service.load)
        logger.info("[3/4] Piper TTS ready")
    except Exception as e:
        logger.error(f"[3/4] TTS load failed: {e}")

    # Load LLM — slowest, ~10–30s on CPU
    logger.info("[4/4] Loading LLM (this may take 10–30s on CPU)...")
    try:
        await loop.run_in_executor(None, llm_service.load)
        logger.info("[4/4] LLM ready")
    except Exception as e:
        logger.error(f"[4/4] LLM load failed: {e}")

    logger.info("=" * 50)
    logger.info(f"Server ready at http://{settings.HOST}:{settings.PORT}")
    logger.info(f"WebSocket endpoint: ws://{settings.HOST}:{settings.PORT}/ws/interview")
    logger.info(f"API docs: http://{settings.HOST}:{settings.PORT}/docs")
    logger.info("=" * 50)

    yield  # App runs here

    logger.info("Shutting down...")


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title="AI Interviewer",
    description="Real-time voice-based AI interview system",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────
# Allow all origins for local dev.
# In production, restrict to your frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(ws_router)
app.include_router(upload_router)
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "service": "AI Interviewer Backend",
        "status": "running",
        "device": settings.DEVICE,
        "docs": "/docs",
        "websocket": "/ws/interview",
    }


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
