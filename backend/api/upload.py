"""
api/upload.py
─────────────
HTTP endpoints for uploading resume and job description.

POST /upload/resume      → parses file, stores text in session
POST /upload/jd          → stores raw job description text in session

These are called BEFORE starting the WebSocket connection.
The session_id ties the uploaded context to the WS interview session.
"""

import uuid
import aiofiles
import asyncio
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from core.config import settings
from core.session_manager import session_manager
from utils.resume_parser import parse_resume
from utils.logger import get_logger
from services.llm_service import llm_service

logger = get_logger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

async def _extract_name_via_llm(resume_text: str) -> str:
    """Uses the local LLM to reliably extract the candidate name, bypassing PDF layout quirks."""
    if not resume_text:
        return ""
        
    prompt = (
        "Identify the candidate's full name from the following resume text. "
        "Reply with ONLY their name, and absolutely nothing else. "
        "Do not include punctuation or titles. "
        "If you cannot determine a person's name, reply with 'Unknown'.\n\n"
        f"Resume text:\n{resume_text[:2000]}"
    )
    
    # Run blocking inference in a background thread to keep FastAPI responsive
    messages = [{"role": "user", "content": prompt}]
    try:
        raw_name = await asyncio.to_thread(llm_service.generate, messages, False)
        name = raw_name.strip()
        
        # Cleanup in case the LLM ignored instructions and answered verbosely
        if "name is" in name.lower():
            name = name.split("is")[-1].strip(" '\".,\n")
        if name.lower() == "unknown":
            return ""
            
        # Ensure it's not a hallucinated full paragraph
        if len(name) > 40 or "\n" in name:
            return ""
            
        logger.info(f"LLM extracted candidate name: '{name}'")
        return name
    except Exception as e:
        logger.error(f"Failed to extract name via LLM: {e}")
        return ""

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


@router.post("/session")
async def create_session():
    """
    Create a blank interview session.
    Returns session_id used by all subsequent upload + WS calls.
    No request body needed.
    """
    session = session_manager.create()
    logger.info(f"Session created via HTTP: {session.session_id[:8]}")
    return {"session_id": session.session_id}


@router.get("/session")
async def create_session_get():
    """GET variant — easier to call from browser / test."""
    session = session_manager.create()
    logger.info(f"Session created via HTTP GET: {session.session_id[:8]}")
    return {"session_id": session.session_id}


@router.post("/resume")
async def upload_resume(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload and parse a resume file (PDF / DOCX / TXT).
    Extracted text is attached to the session for LLM context.
    """
    # Validate session
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_MB} MB",
        )

    # Save to disk (optional — useful for debugging)
    save_path = Path(settings.UPLOAD_DIR) / f"{session_id}_resume{ext}"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(file_bytes)

    # Parse
    resume_text = parse_resume(file_bytes, file.filename or "resume.pdf")
    if not resume_text:
        raise HTTPException(status_code=422, detail="Could not extract text from file")

    # Store in session
    session.resume_text = resume_text
    session.candidate_name = await _extract_name_via_llm(resume_text)

    name_log = f" | name='{session.candidate_name}'" if session.candidate_name else ""
    logger.info(
        f"Resume uploaded for session {session_id[:8]}: "
        f"{len(resume_text)} chars from '{file.filename}'{name_log}"
    )

    return {
        "status": "ok",
        "session_id": session_id,
        "chars_extracted": len(resume_text),
        "preview": resume_text[:200] + "..." if len(resume_text) > 200 else resume_text,
    }


@router.post("/jd")
async def upload_job_description(
    session_id: str = Form(...),
    job_description: str = Form(...),
):
    """
    Submit a job description as plain text.
    Stored in the session and injected into the LLM prompt.
    """
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    jd = job_description.strip()
    if not jd:
        raise HTTPException(status_code=400, detail="Job description cannot be empty")

    if len(jd) > 5000:
        jd = jd[:5000]
        logger.warning(f"JD truncated to 5000 chars for session {session_id[:8]}")

    session.job_description = jd
    logger.info(f"JD saved for session {session_id[:8]}: {len(jd)} chars")

    return {
        "status": "ok",
        "session_id": session_id,
        "chars_saved": len(jd),
    }


@router.get("/status/{session_id}")
async def session_status(session_id: str):
    """Check what context has been uploaded for a session."""
    session = session_manager.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "has_resume": bool(session.resume_text),
        "has_jd": bool(session.job_description),
        "resume_chars": len(session.resume_text),
        "jd_chars": len(session.job_description),
        "question_count": session.question_count,
        "is_active": session.is_active,
    }
