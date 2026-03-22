"""
api/health.py
─────────────
Health check and system status endpoints.

GET /health         → basic liveness check
GET /health/models  → verify all AI models are loaded and ready
GET /health/system  → CPU / RAM usage snapshot
"""

import os
import platform
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pathlib import Path

from core.config import settings
from core.session_manager import session_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    """Basic liveness probe."""
    return {"status": "ok", "device": settings.DEVICE}


@router.get("/models")
async def model_status():
    """Check which model files are present on disk."""

    def check(path: str) -> dict:
        p = Path(path)
        return {
            "path": str(p),
            "exists": p.exists(),
            "size_mb": round(p.stat().st_size / 1024 / 1024, 1) if p.exists() else 0,
        }

    llm = check(settings.LLM_MODEL_PATH)
    whisper_dir = Path(settings.WHISPER_MODEL_PATH)
    whisper_files = list(whisper_dir.glob("**/*")) if whisper_dir.exists() else []
    tts_onnx = check(settings.TTS_MODEL_PATH)
    tts_json = check(settings.TTS_CONFIG_PATH)

    all_ready = (
        llm["exists"]
        and len(whisper_files) > 0
        and tts_onnx["exists"]
        and tts_json["exists"]
    )

    return {
        "all_ready": all_ready,
        "llm": llm,
        "whisper": {
            "dir": str(whisper_dir),
            "exists": whisper_dir.exists(),
            "file_count": len(whisper_files),
        },
        "tts_onnx": tts_onnx,
        "tts_json": tts_json,
    }


@router.get("/system")
async def system_info():
    """Return CPU, RAM, and session stats."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.2)
        ram_info = {
            "total_gb": round(mem.total / 1e9, 1),
            "available_gb": round(mem.available / 1e9, 1),
            "used_pct": mem.percent,
        }
    except ImportError:
        cpu_pct = None
        ram_info = {"note": "install psutil for RAM stats"}

    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "device": settings.DEVICE,
        "cpu_percent": cpu_pct,
        "ram": ram_info,
        "active_sessions": session_manager.count(),
        "llm_threads": settings.LLM_N_THREADS,
        "llm_gpu_layers": settings.LLM_N_GPU_LAYERS,
    }
