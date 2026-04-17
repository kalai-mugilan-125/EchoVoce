# EchoVoce

EchoVoce is a full-stack, real-time AI interviewer that runs locally.
It uses voice input from the browser, transcribes speech, generates interview questions with a local LLM, and streams spoken AI responses back to the user.

## What it does

- Creates interview sessions over HTTP.
- Accepts optional resume upload (PDF, DOC, DOCX, TXT).
- Accepts optional job description text.
- Runs a live voice interview over WebSocket.
- Streams partial/final transcripts and AI speech responses.
- Supports interview styles: mixed, technical, hr.

## Tech stack

| Layer | Tools |
|---|---|
| Frontend | React + Vite |
| Backend API | FastAPI + Uvicorn |
| LLM | llama-cpp-python (GGUF models) |
| Speech-to-text | faster-whisper |
| Text-to-speech | piper-tts |
| Voice activity detection | silero-vad |

## Project structure

```text
EchoVoce-main/
  backend/
    api/              # REST + WebSocket routes
    core/             # config, session manager, prompt builder
    services/         # LLM/STT/TTS/VAD service wrappers
    utils/            # logging, audio + resume parsing helpers
    download_models.py
    main.py
    requirements.txt

  frontend/
    src/components/   # setup/interview/end screens
    src/hooks/        # interview WebSocket + audio logic
    src/utils/        # REST client helpers
    vite.config.js
    package.json
```

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer (Node.js 20 recommended)
- npm
- Microphone access in browser
- At least 8 GB RAM (16 GB recommended)
- Around 8 GB free disk space for local AI models

## Quick start

### 1) Start backend

Open a terminal in `backend` and run:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python download_models.py
uvicorn main:app --host 0.0.0.0 --port 8000
```

Create `backend/.env` if you want to override defaults.
Only `backend/.env` is loaded (do not use `.env.local`).

```env
DEVICE=cpu
LLM_N_THREADS=4
PORT=8000
```

Backend will be available at:

- API root: http://localhost:8000
- Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/interview

Notes:

- `download_models.py` downloads LLM, Whisper, and Piper assets.
- Backend reads optional environment overrides from `backend/.env` only.

### 2) Start frontend

Open another terminal in `frontend` and run:

```powershell
npm install
npm run dev
```

Frontend dev app runs at:

- http://localhost:5173

### 3) Use the app

1. Open the frontend URL.
2. Optionally upload a resume.
3. Optionally paste a job description.
4. Pick interview style.
5. Start interview, record your answer, then submit.

## API overview

Base URL: `http://localhost:8000`

### Session and upload endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/upload/session` | Create session and return `session_id` |
| GET | `/upload/session` | Alternate session creation endpoint |
| POST | `/upload/resume` | Upload and parse resume for a session |
| POST | `/upload/jd` | Save job description for a session |
| GET | `/upload/status/{session_id}` | Check session context state |

### Health endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Basic liveness check |
| GET | `/health/models` | Verify model files are present |
| GET | `/health/system` | Runtime and resource stats |

## WebSocket protocol

Connect to:

`ws://localhost:8000/ws/interview`

Client messages:

- `{"type":"start","session_id":"...","style":"mixed|technical|hr"}`
- Binary PCM audio frames (int16, mono)
- `{"type":"submit_answer"}`
- `{"type":"interrupt"}`
- `{"type":"ping"}`
- `{"type":"end"}`

Server messages:

- `{"type":"ready","session_id":"..."}`
- `{"type":"transcript_partial","text":"..."}`
- `{"type":"transcript","text":"..."}`
- `{"type":"tts_start","sentence":"..."}`
- Binary WAV chunks
- `{"type":"tts_end"}`
- `{"type":"listening"}`
- `{"type":"interrupt_ack"}`
- `{"type":"pong"}`
- `{"type":"error","message":"..."}`

## Configuration

Backend defaults are defined in `backend/core/config.py` and can be overridden using `backend/.env` only (no `.env.local`).

Common variables:

- `DEVICE=cpu|cuda`
- `LLM_MODEL_PATH=models/llm/mistral-7b-instruct-v0.2.Q4_K_M.gguf`
- `LLM_N_THREADS=4`
- `LLM_N_GPU_LAYERS=0`
- `WHISPER_MODEL_SIZE=small`
- `WHISPER_DEVICE=cpu`
- `WHISPER_COMPUTE_TYPE=int8`
- `PORT=8000`

## Frontend/backend connection details

- Frontend REST calls use Vite proxy for `/upload` and `/health`.
- Frontend WebSocket URL is currently hardcoded in `frontend/src/hooks/useInterview.js` as `ws://localhost:8000/ws/interview`.
- If backend host/port changes, update that constant.

## Troubleshooting

- WebSocket connection failed:
  - Ensure backend is running on port 8000.
  - Check browser console for blocked mixed-content or network errors.

- No transcript or poor transcription:
  - Verify microphone permission is allowed.
  - Speak clearly and submit after recording.

- Model errors on startup:
  - Run `python download_models.py` again.
  - Confirm model files exist under `backend/models`.

- Frontend API calls fail in dev:
  - Confirm Vite dev server is running on 5173.
  - Confirm backend is reachable at `http://localhost:8000`.

## Development notes

- Backend model loading happens at startup in `backend/main.py`.
- One LLM inference runs at a time (thread lock) to avoid llama-cpp concurrency issues.
- Session state is in-memory and cleared when session ends.

## License

No license file is currently included in this repository.
