"""Intent classifier and lead scoring (run after every 3rd message)."""
import os
import json
import re
import logging
from app.models.schemas import IntentResult, ExtractedProfile
from app.utils.memory import get_full_context_for_llm

import anthropic

logger = logging.getLogger(__name__)
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

INTENT_PROMPT = """You are analyzing a study-abroad counselling conversation. Extract intent and profile. Reply with valid JSON only, no markdown.

Scoring signals (add to lead_score):
+10 IELTS or PTE score mentioned
+10 percentage or GPA mentioned
+10 budget or lakhs mentioned
+5 specific country mentioned
+5 specific course mentioned
+15 specific intake (e.g. Fall 2025)
+10 urgency: urgent, this month, asap
+20 asks about IVY Overseas services
+25 asks to book counselling session
+25 shares 10-digit phone number

Intent levels by score: 0-30 BROWSING, 31-50 RESEARCHING, 51-60 CONSIDERING, 61-100 HOT_LEAD.

Output JSON exactly:
{
  "intent_level": "BROWSING|RESEARCHING|CONSIDERING|HOT_LEAD",
  "lead_score": 0,
  "extracted_profile": {
    "name": null,
    "phone": null,
    "email": null,
    "target_course": null,
    "target_country": null,
    "target_intake": null,
    "budget_inr": null,
    "ielts_score": null,
    "percentage": null
  },
  "conversation_summary": "2 sentence summary",
  "recommended_action": "what counsellor should do"
}
"""


def _parse_json_from_text(text: str) -> dict:
    text = text.strip()
    # Strip markdown code block if present
    if "```" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
    return json.loads(text)


async def run_intent(session_id: str) -> IntentResult | None:
    """Call Claude with conversation history; return IntentResult."""
    messages = get_full_context_for_llm(session_id)
    if not messages:
        return None
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        client = anthropic.AsyncAnthropic(api_key=key)
        # Build single user message with conversation
        conv_text = "\n".join(
            f"{m['role']}: {m['content'][:300]}" for m in messages[-20:]
        )
        r = await client.messages.create(
            model=MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": INTENT_PROMPT + "\n\nConversation:\n" + conv_text}],
        )
        text = r.content[0].text if r.content else "{}"
        data = _parse_json_from_text(text)
        ep = data.get("extracted_profile") or {}
        profile = ExtractedProfile(
            name=ep.get("name"),
            phone=ep.get("phone"),
            email=ep.get("email"),
            target_course=ep.get("target_course"),
            target_country=ep.get("target_country"),
            target_intake=ep.get("target_intake"),
            budget_inr=ep.get("budget_inr"),
            ielts_score=ep.get("ielts_score"),
            percentage=ep.get("percentage"),
        )
        return IntentResult(
            intent_level=data.get("intent_level", "BROWSING"),
            lead_score=int(data.get("lead_score", 0)),
            extracted_profile=profile,
            conversation_summary=data.get("conversation_summary", ""),
            recommended_action=data.get("recommended_action", ""),
        )
    except Exception as e:
        logger.warning("Intent run failed: %s", e)
        return None
