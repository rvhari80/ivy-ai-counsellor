"""SQLite tables and helpers for IVY AI Counsellor."""
import os
import aiosqlite
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./ivy_counsellor.db")
# aiosqlite uses file path; strip protocol
DB_PATH = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    user_message  TEXT NOT NULL,
    ai_response   TEXT NOT NULL,
    intent_level  TEXT,
    lead_score    INTEGER DEFAULT 0,
    rag_score     REAL,
    fallback_type TEXT,
    platform      TEXT DEFAULT 'web',
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leads (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           TEXT UNIQUE NOT NULL,
    name                 TEXT,
    phone                TEXT,
    email                TEXT,
    target_course         TEXT,
    target_country        TEXT,
    target_intake         TEXT,
    budget_inr            INTEGER,
    ielts_score           TEXT,
    percentage            TEXT,
    lead_score            INTEGER DEFAULT 0,
    intent_level          TEXT,
    conversation_summary  TEXT,
    recommended_action    TEXT,
    notified_at           DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unanswered_queries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text       TEXT NOT NULL,
    similarity_score REAL,
    fallback_type    TEXT,
    session_id       TEXT,
    status           TEXT DEFAULT 'PENDING',
    timestamp        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pdf_library (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_id      TEXT UNIQUE NOT NULL,
    filename    TEXT NOT NULL,
    category    TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'ACTIVE',
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(lead_score DESC);
CREATE INDEX IF NOT EXISTS idx_unans_time ON unanswered_queries(timestamp);
"""


async def init_db():
    """Create all tables on app startup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db():
    """Async context manager for DB connection."""
    conn = await aiosqlite.connect(DB_PATH)
    try:
        yield conn
    finally:
        await conn.close()


async def save_conversation(
    conn,
    session_id: str,
    user_message: str,
    ai_response: str,
    intent_level: str | None = None,
    lead_score: int = 0,
    rag_score: float | None = None,
    fallback_type: str | None = None,
    platform: str = "web",
):
    await conn.execute(
        """INSERT INTO conversations
           (session_id, user_message, ai_response, intent_level, lead_score, rag_score, fallback_type, platform)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, user_message, ai_response, intent_level, lead_score, rag_score, fallback_type, platform),
    )
    await conn.commit()


async def upsert_lead(
    conn,
    session_id: str,
    name: str | None,
    phone: str | None,
    email: str | None,
    target_course: str | None,
    target_country: str | None,
    target_intake: str | None,
    budget_inr: int | None,
    ielts_score: str | None,
    percentage: str | None,
    lead_score: int,
    intent_level: str,
    conversation_summary: str | None,
    recommended_action: str | None,
    notified_at: str | None = None,
):
    await conn.execute(
        """INSERT INTO leads (
            session_id, name, phone, email, target_course, target_country,
            target_intake, budget_inr, ielts_score, percentage, lead_score,
            intent_level, conversation_summary, recommended_action, notified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            name=excluded.name, phone=excluded.phone, email=excluded.email,
            target_course=excluded.target_course, target_country=excluded.target_country,
            target_intake=excluded.target_intake, budget_inr=excluded.budget_inr,
            ielts_score=excluded.ielts_score, percentage=excluded.percentage,
            lead_score=excluded.lead_score, intent_level=excluded.intent_level,
            conversation_summary=excluded.conversation_summary,
            recommended_action=excluded.recommended_action,
            notified_at=COALESCE(excluded.notified_at, notified_at)
        """,
        (
            session_id, name, phone, email, target_course, target_country,
            target_intake, budget_inr, ielts_score, percentage, lead_score,
            intent_level, conversation_summary, recommended_action, notified_at,
        ),
    )
    await conn.commit()


async def log_unanswered(conn, query_text: str, similarity_score: float | None, fallback_type: str | None, session_id: str | None):
    await conn.execute(
        """INSERT INTO unanswered_queries (query_text, similarity_score, fallback_type, session_id)
           VALUES (?, ?, ?, ?)""",
        (query_text, similarity_score, fallback_type, session_id),
    )
    await conn.commit()


async def get_lead_by_session(conn, session_id: str):
    cursor = await conn.execute(
        "SELECT * FROM leads WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    return row


async def set_lead_notified(conn, session_id: str, notified_at: str):
    await conn.execute(
        "UPDATE leads SET notified_at = ? WHERE session_id = ?",
        (notified_at, session_id),
    )
    await conn.commit()
