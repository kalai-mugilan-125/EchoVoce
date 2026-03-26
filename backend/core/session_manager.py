"""
core/session_manager.py
───────────────────────
Manages per-user interview sessions.

Each WebSocket connection gets a unique Session that holds:
  • conversation history  (fed to LLM each turn)
  • parsed resume text    (injected into system prompt)
  • job description text
  • interview state       (question count, is_speaking flag for interrupts)
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    role: str          # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InterviewSession:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Context injected into LLM
    resume_text: str = ""
    job_description: str = ""
    candidate_name: str = ""  # extracted from resume; injected explicitly into prompt

    # Conversation history (kept trimmed to avoid context overflow)
    history: list[Message] = field(default_factory=list)

    # Interview state
    question_count: int = 0
    is_ai_speaking: bool = False   # True while TTS audio is streaming out
    is_active: bool = True

    # Interrupt flag: set True when user speaks while AI is talking
    interrupt_requested: bool = False

    # ── Token-budget-aware history trimming ──────────────────
    # n_ctx=163840 total. We reserve:
    #   ~2500 tokens for system prompt (base + resume + JD)
    #   ~512  tokens for the next LLM response
    # That leaves ~130000 tokens for actual conversation history.
    # Rough estimate: 1 token ≈ 4 chars.
    HISTORY_TOKEN_BUDGET = 130000
    CHARS_PER_TOKEN      = 4

    def add_message(self, role: str, content: str):
        self.history.append(Message(role=role, content=content))
        self._trim_history()

    def _trim_history(self):
        """Keep the system prompt + as many recent messages as fit in budget."""
        if not self.history:
            return

        # Always keep the system prompt (index 0)
        system = self.history[:1]
        turns  = self.history[1:]

        budget_chars = self.HISTORY_TOKEN_BUDGET * self.CHARS_PER_TOKEN

        # Walk from newest → oldest, accumulate until budget exceeded
        kept: list[Message] = []
        used = 0
        for msg in reversed(turns):
            msg_chars = len(msg.content)
            if used + msg_chars > budget_chars and kept:
                break   # stop before exceeding; always keep at least 1 turn
            kept.append(msg)
            used += msg_chars

        self.history = system + list(reversed(kept))

    def get_history_dicts(self) -> list[dict]:
        """Return history as list of {role, content} for LLM input."""
        return [{"role": m.role, "content": m.content} for m in self.history]

    def request_interrupt(self):
        """Called by VAD when user starts speaking while AI is talking."""
        if self.is_ai_speaking:
            self.interrupt_requested = True

    def clear_interrupt(self):
        self.interrupt_requested = False
        self.is_ai_speaking = False

    def has_context(self) -> bool:
        return bool(self.resume_text or self.job_description)


class SessionManager:
    """
    Global registry of active interview sessions.
    One session per WebSocket connection.
    """

    def __init__(self):
        self._sessions: dict[str, InterviewSession] = {}

    def create(self) -> InterviewSession:
        session = InterviewSession()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[InterviewSession]:
        return self._sessions.get(session_id)

    def delete(self, session_id: str):
        self._sessions.pop(session_id, None)

    def set_context(
        self,
        session_id: str,
        resume_text: str = "",
        job_description: str = ""
    ) -> bool:
        session = self.get(session_id)
        if not session:
            return False
        session.resume_text = resume_text
        session.job_description = job_description
        return True

    def count(self) -> int:
        return len(self._sessions)


# Singleton — imported by services and routes
session_manager = SessionManager()
