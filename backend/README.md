# AI Interviewer — Backend

Real-time voice-based AI interview system.
Runs fully locally — no cloud API required.

## Stack

| Component | Library         | CPU support |
|-----------|----------------|-------------|
| LLM       | llama-cpp-python (GGUF) | Yes (int4)  |
| STT       | faster-whisper  | Yes (int8)  |
| TTS       | Piper TTS       | Yes (ONNX)  |
| VAD       | Silero VAD      | Yes (LSTM)  |
| Server    | FastAPI + uvicorn | —          |

---

## Setup

### 1. Requirements
- Python 3.10+
- 8 GB RAM minimum (16 GB recommended)
- ~8 GB free disk space for models

### 2. Install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> For GPU acceleration (optional):
> ```bash
> CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python --force-reinstall
> ```

### 3. Configure

```bash
cp .env .env.local
# Edit .env — set DEVICE=cpu or DEVICE=cuda
# Set LLM_N_THREADS to your CPU core count
```

### 4. Download models

```bash
python download_models.py
```

This downloads:
- Mistral-7B-Instruct Q4_K_M (~4.1 GB) → `models/llm/`
- faster-whisper small (~500 MB)       → `models/whisper/`
- Piper en_US-lessac-medium (~60 MB)   → `models/tts/`

### 5. Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Server starts at: `http://localhost:8000`
WebSocket at:     `ws://localhost:8000/ws/interview`
API docs at:      `http://localhost:8000/docs`

---

## API Reference

### HTTP Endpoints

| Method | Path                        | Description                  |
|--------|-----------------------------|------------------------------|
| POST   | `/upload/session`           | Create a new interview session |
| POST   | `/upload/resume`            | Upload resume (PDF/DOCX/TXT) |
| POST   | `/upload/jd`                | Submit job description text  |
| GET    | `/upload/status/{session_id}` | Check session context status |
| GET    | `/health`                   | Liveness check               |
| GET    | `/health/models`            | Model file status            |
| GET    | `/health/system`            | CPU/RAM/session stats        |

### WebSocket Protocol

Connect to: `ws://localhost:8000/ws/interview`

**Client → Server:**
```json
{ "type": "start", "session_id": "...", "style": "mixed" }
```
Then send raw PCM int16 audio binary frames (16kHz mono).
```json
{ "type": "end" }
```

**Server → Client:**
```json
{ "type": "ready", "session_id": "..." }
{ "type": "transcript", "text": "..." }
{ "type": "tts_start", "sentence": "..." }
<binary WAV frame>
{ "type": "tts_end" }
{ "type": "interrupt_ack" }
```

---

## Switching models

Edit `.env`:

```bash
# Use LLaMA 3.1 8B instead of Mistral
LLM_MODEL_PATH=models/llm/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf

# Use larger Whisper for better accuracy
WHISPER_MODEL_SIZE=medium

# Enable GPU (if available)
DEVICE=cuda
LLM_N_GPU_LAYERS=-1
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

---

## Expose via Cloudflare Tunnel (free public URL)

```bash
# Install cloudflared once
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

cloudflared tunnel --url http://localhost:8000
# Returns: https://random-name.trycloudflare.com
```

Point your frontend `WS_URL` to `wss://random-name.trycloudflare.com/ws/interview`.
