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
"""

from core.session_manager import InterviewSession

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

STYLE_PROMPTS = {
    "technical": "Focus on technical depth, system design, coding knowledge, and problem-solving.",
    "hr":        "Focus on soft skills, culture fit, past behaviour, and career goals.",
    "mixed":     "Balance technical questions with behavioural and situational questions.",
}


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

    if session.has_context():
        if session.resume_text:
            prompt += RESUME_BLOCK.format(resume=session.resume_text[:3000])
        if session.job_description:
            prompt += JD_BLOCK.format(jd=session.job_description[:1500])
    else:
        prompt += NO_CONTEXT_NOTE

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
