"""Fallback responses when RAG confidence is low."""
import os
import json
import logging
from typing import Literal

import anthropic

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
Categories: study_abroad | off_topic | sensitive

User message:
"""
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


async def classify_query(query: str) -> Literal["study_abroad", "off_topic", "sensitive"]:
    """Call Claude to classify query."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return "study_abroad"
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        r = await client.messages.create(
            model=MODEL,
            max_tokens=20,
            messages=[{"role": "user", "content": CLASSIFY_PROMPT + query[:500]}],
        )
        text = (r.content[0].text if r.content else "").strip().lower()
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
