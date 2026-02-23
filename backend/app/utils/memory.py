"""Session conversation store with summarization and expiry."""
import os
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_PAIRS = 10
IDLE_EXPIRE_SECONDS = 30 * 60  # 30 minutes

# In-process store: session_id -> { "pairs": [...], "last_activity": ts }
_sessions: dict[str, dict[str, Any]] = {}


def _ensure_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"pairs": [], "last_activity": time.time()}
    _sessions[session_id]["last_activity"] = time.time()
    return _sessions[session_id]


def add_message_pair(session_id: str, user: str, assistant: str) -> None:
    data = _ensure_session(session_id)
    data["pairs"].append({"role": "user", "content": user})
    data["pairs"].append({"role": "assistant", "content": assistant})
    while len(data["pairs"]) > MAX_PAIRS * 2:
        data["pairs"] = data["pairs"][2:]


def get_messages(session_id: str) -> list[dict[str, str]]:
    """Return list of {role, content} for context (last MAX_PAIRS pairs)."""
    data = _ensure_session(session_id)
    return list(data["pairs"])


def set_summary_as_system(session_id: str, summary: str) -> None:
    """Replace old pairs with a single system summary and keep recent pairs."""
    data = _ensure_session(session_id)
    # Keep only last 2 pairs (4 messages), prepend summary as synthetic system
    keep = min(4, len(data["pairs"]))
    data["pairs"] = data["pairs"][-keep:] if keep else []
    data["summary"] = summary


def get_summary(session_id: str) -> str | None:
    return _sessions.get(session_id, {}).get("summary")


def get_full_context_for_llm(session_id: str) -> list[dict[str, str]]:
    """Messages for Claude: optional summary as system, then recent pairs."""
    data = _ensure_session(session_id)
    out = []
    if data.get("summary"):
        out.append({"role": "user", "content": f"[Previous context summary: {data['summary']}]"})
        # Claude API uses user/assistant; we inject summary as user for simplicity
    for m in data["pairs"]:
        out.append({"role": m["role"], "content": m["content"]})
    return out


def expire_idle_sessions() -> None:
    now = time.time()
    to_del = [sid for sid, d in _sessions.items() if now - d["last_activity"] > IDLE_EXPIRE_SECONDS]
    for sid in to_del:
        del _sessions[sid]
    if to_del:
        logger.info("Expired sessions: count=%s", len(to_del))
