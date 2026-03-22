"""
download_models.py
──────────────────
Run once before starting the server:
    python download_models.py

Downloads:
  • Mistral-7B-Instruct Q4_K_M  (LLM)
  • faster-whisper small        (STT)
  • Piper en_US-lessac-medium   (TTS)
"""

import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path("models")

LLM_URL = (
    "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
    "/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
)
LLM_PATH = MODELS_DIR / "llm" / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"

TTS_ONNX_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    "/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
)
TTS_JSON_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main"
    "/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
)
TTS_ONNX_PATH = MODELS_DIR / "tts" / "en_US-lessac-medium.onnx"
TTS_JSON_PATH = MODELS_DIR / "tts" / "en_US-lessac-medium.onnx.json"


def progress_hook(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(downloaded / total_size * 100, 100)
        bar = "#" * int(pct / 2)
        sys.stdout.write(f"\r  [{bar:<50}] {pct:.1f}%")
        sys.stdout.flush()
    if downloaded >= total_size:
        print()


def download(url: str, dest: Path, label: str):
    if dest.exists():
        print(f"  [skip] {label} already exists at {dest}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {label}...")
    print(f"  Source: {url}")
    urllib.request.urlretrieve(url, dest, reporthook=progress_hook)
    print(f"  Saved → {dest}")


def download_whisper():
    """faster-whisper downloads models from HuggingFace on first use via its own API."""
    from faster_whisper import WhisperModel
    whisper_path = MODELS_DIR / "whisper"
    whisper_path.mkdir(parents=True, exist_ok=True)
    if any(whisper_path.iterdir()):
        print("  [skip] Whisper model already cached.")
        return
    print("  Downloading faster-whisper small model (auto-cached)...")
    WhisperModel("small", device="cpu", compute_type="int8",
                 download_root=str(whisper_path))
    print("  Whisper model saved.")


if __name__ == "__main__":
    print("\n=== AI Interviewer — Model Downloader ===\n")

    print("[1/3] LLM — Mistral 7B Instruct Q4_K_M (~4.1 GB)")
    download(LLM_URL, LLM_PATH, "Mistral-7B Q4_K_M")

    print("\n[2/3] STT — faster-whisper small (~500 MB)")
    try:
        download_whisper()
    except Exception as e:
        print(f"  Warning: {e}")
        print("  Whisper will auto-download on first server start.")

    print("\n[3/3] TTS — Piper en_US-lessac-medium (~60 MB)")
    download(TTS_ONNX_URL, TTS_ONNX_PATH, "Piper ONNX model")
    download(TTS_JSON_URL, TTS_JSON_PATH, "Piper config JSON")

    print("\n=== All models ready. Run: uvicorn main:app --reload ===\n")
