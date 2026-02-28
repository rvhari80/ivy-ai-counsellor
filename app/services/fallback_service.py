"""Fallback responses when RAG confidence is low."""
import os
import logging
from typing import Literal
from openai import AsyncOpenAI
from app.models.database import get_db, log_unanswered

logger = logging.getLogger(__name__)

THRESHOLDS = {
    "DIRECT": 0.75,
    "PARTIAL": 0.50,
    "GAP": 0.30,
}

TEMPLATES = {
    "PARTIAL": "Based on available information, {info}. "
    "For the most accurate details, our counsellors can help. "
    "Can I arrange a free call?",
    "GAP": "Great question! I don't have that detail right now. "
    "Our specialist counsellor would know this. "
    "Shall I connect you? It's completely free.",
    "OFF_TOPIC": "That's a bit outside my area! I'm IVY's study abroad "
    "assistant. Can I help you with universities, visas, "
    "scholarships or IELTS instead?",
    "ESCALATE": "This situation needs personalised attention from our team. "
    "Can I have a counsellor call you directly? "
    "Please share your name and number.",
}

CLASSIFY_PROMPT = """Classify this user message into exactly one category. Reply with only one word.

Categories:
- study_abroad: questions about universities, visas, IELTS, scholarships, courses, countries, applications
- off_topic: cricket, weather, jokes, cooking, sports, movies, anything unrelated to studying abroad
- sensitive: visa rejection, mental health distress, financial crisis, depression, extreme stress, hopelessness, cannot afford, devastated, don't know what to do

Examples:
"What IELTS score for Australia" -> study_abroad
"What is cricket score" -> off_topic
"My visa got rejected I am devastated" -> sensitive
"I cannot afford fees I am very stressed" -> sensitive
"I feel hopeless about my future" -> sensitive

Reply with ONLY one word: study_abroad or off_topic or sensitive

User message:
"""


async def classify_query(query: str) -> Literal["study_abroad", "off_topic", "sensitive"]:
    """Call OpenAI to classify query."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return "study_abroad"
    try:
        client = AsyncOpenAI(api_key=key)
        r = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=20,
            messages=[
                {
                    "role": "system",
                    "content": "You classify messages. Reply with only one word: study_abroad or off_topic or sensitive"
                },
                {
                    "role": "user",
                    "content": CLASSIFY_PROMPT + query[:500]
                }
            ],
        )
        text = (r.choices[0].message.content or "").strip().lower()
        if "off_topic" in text or "off topic" in text:
            return "off_topic"
        if "sensitive" in text:
            return "sensitive"
        return "study_abroad"
    except Exception as e:
        logger.warning("Classify failed: %s", e)
        return "study_abroad"


async def get_fallback_response(
    query: str,
    best_score: float,
    session_id: str | None = None,
) -> str:
    """Return fallback message and log to unanswered_queries."""
    classification = await classify_query(query)
    if classification == "off_topic":
        msg = TEMPLATES["OFF_TOPIC"]
        fallback_type = "OFF_TOPIC"
    elif classification == "sensitive":
        msg = TEMPLATES["ESCALATE"]
        fallback_type = "ESCALATE"
    elif best_score >= THRESHOLDS["PARTIAL"]:
        msg = TEMPLATES["PARTIAL"].format(info="here's what I found.")
        fallback_type = "PARTIAL"
    else:
        msg = TEMPLATES["GAP"]
        fallback_type = "GAP"

    async with get_db() as conn:
        await log_unanswered(conn, query, best_score, fallback_type, session_id)
    return msg