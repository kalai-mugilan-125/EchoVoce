"""
core/prompt_builder.py
──────────────────────
Builds the LLM system prompt dynamically from:
  • resume text
  • job description
  • interview mode / tone

The system prompt is injected as the first message in every conversation.
It tells the LLM to act as a professional interviewer and base all
questions on the candidate's resume and the role they applied for.

Changes vs v1:
  • Resume limit raised 3000 → 6000 chars (covers a full 2-page resume)
  • JD limit raised 1500 → 3000 chars
  • Truncation happens at the last paragraph boundary, not mid-sentence
  • build_system_prompt() logs exactly how many chars were injected
"""

from utils.logger import get_logger
from core.session_manager import InterviewSession

logger = get_logger(__name__)


INTERVIEWER_BASE = """You are a professional AI interviewer conducting a real-time voice interview.

RULES YOU MUST FOLLOW:
1. Ask ONE question at a time — never multiple questions in one response.
2. Keep responses concise (2–4 sentences max). You are speaking out loud.
3. Base every question on the candidate's resume and job description below.
4. Start with a warm greeting, then ask the first question.
5. Progressively deepen questions: start broad → get technical → behavioural.
6. When the candidate gives a vague answer, ask a specific follow-up.
7. Never repeat a question already asked in this session.
8. Do NOT use bullet points, numbered lists, or markdown. Plain text only.
9. Do NOT say "Great answer!" or "That's interesting!" — avoid filler praise.
10. End the interview after 8–10 questions by thanking the candidate.

INTERVIEW STYLE: {style}
"""

RESUME_BLOCK = """
─── CANDIDATE RESUME ───────────────────────────────────────
{resume}
────────────────────────────────────────────────────────────
"""

JD_BLOCK = """
─── JOB DESCRIPTION ────────────────────────────────────────
{jd}
────────────────────────────────────────────────────────────
"""

NO_CONTEXT_NOTE = """
No resume or job description was provided.
Conduct a general professional interview covering:
  • background and experience
  • technical skills
  • problem-solving approach
  • teamwork and communication
"""

INTERVIEW_TARGET = "The candidate's name is {name}."

STYLE_PROMPTS = {
    "technical": "Focus on technical depth, system design, coding knowledge, and problem-solving.",
    "hr":        "Focus on soft skills, culture fit, past behaviour, and career goals.",
    "mixed":     "Balance technical questions with behavioural and situational questions.",
}

# Character limits — high enough to cover a 2-page resume and a detailed JD
RESUME_CHAR_LIMIT = 6000
JD_CHAR_LIMIT     = 3000


def _truncate_at_paragraph(text: str, limit: int) -> str:
    """
    Truncate `text` to at most `limit` chars, but break at the last complete
    paragraph boundary (double newline or single newline before a short line)
    rather than mid-sentence. Appends "..." if truncated.
    """
    if len(text) <= limit:
        return text

    # Try to cut at a paragraph break
    candidate = text[:limit]
    last_break = max(candidate.rfind("\n\n"), candidate.rfind("\n"))
    if last_break > limit * 0.6:   # only accept if we kept ≥60% of the limit
        return candidate[:last_break].rstrip() + "\n[...truncated]"

    # Fallback: cut at last sentence end
    for end_char in (".", "!", "?"):
        pos = candidate.rfind(end_char)
        if pos > limit * 0.6:
            return candidate[:pos + 1] + " [...]"

    return candidate + " [...]"


def build_system_prompt(
    session: InterviewSession,
    style: str = "mixed"
) -> str:
    """
    Construct the full system prompt for a given session.
    Called once per session when history is initialised.
    """
    style_text = STYLE_PROMPTS.get(style, STYLE_PROMPTS["mixed"])
    prompt = INTERVIEWER_BASE.format(style=style_text)

    if session.candidate_name:
        prompt += "\n" + INTERVIEW_TARGET.format(name=session.candidate_name) + "\n"

    resume_chars = 0
    jd_chars = 0

    if session.has_context():
        if session.resume_text:
            resume_snippet = _truncate_at_paragraph(session.resume_text, RESUME_CHAR_LIMIT)
            prompt += RESUME_BLOCK.format(resume=resume_snippet)
            resume_chars = len(resume_snippet)

        if session.job_description:
            jd_snippet = _truncate_at_paragraph(session.job_description, JD_CHAR_LIMIT)
            prompt += JD_BLOCK.format(jd=jd_snippet)
            jd_chars = len(jd_snippet)
    else:
        prompt += NO_CONTEXT_NOTE

    logger.info(
        f"System prompt built: resume={resume_chars} chars injected "
        f"(raw={len(session.resume_text)}), "
        f"jd={jd_chars} chars injected (raw={len(session.job_description)})"
    )

    return prompt.strip()


def build_interrupt_recovery_prompt() -> str:
    """
    Short injected message used when the user interrupts the AI mid-response.
    Tells the LLM to acknowledge and continue naturally.
    """
    return (
        "The candidate just interrupted you. "
        "Acknowledge briefly in one sentence, then ask your next question."
    )
