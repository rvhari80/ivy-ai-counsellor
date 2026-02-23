"""Weekly gap report: top unanswered queries."""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models.database import get_db, DB_PATH
from app.config.settings import settings
import aiosqlite

logger = logging.getLogger(__name__)


async def get_top_unanswered(days: int = 7, limit: int = 10) -> list[tuple[str, int, str]]:
    """Top unanswered queries by frequency. Returns (query_text, frequency, fallback_type)."""
    async with aiosqlite.connect(DB_PATH) as db:
        since = (datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = await db.execute(
            """SELECT query_text, COUNT(*) as cnt, MAX(fallback_type) as ft
               FROM unanswered_queries
               WHERE date(timestamp) >= date(?)
               GROUP BY LOWER(TRIM(query_text))
               ORDER BY cnt DESC
               LIMIT ?""",
            (since, limit),
        )
        rows = await cursor.fetchall()
    return [(r[0], r[1], r[2] or "") for r in rows]


async def send_gap_report(days: int = 7) -> bool:
    """Email top 10 unanswered to ADMIN_EMAIL."""
    if not settings.SENDGRID_API_KEY or not settings.ADMIN_EMAIL:
        logger.warning("Gap report: SendGrid or ADMIN_EMAIL not set")
        return False
    rows = await get_top_unanswered(days=days, limit=10)
    lines = []
    for i, (q, cnt, ft) in enumerate(rows, 1):
        lines.append(f"{i}. [{cnt}x] {q[:200]}... (fallback: {ft})")
    body = "Top 10 unanswered queries (last %d days):\n\n" % days + "\n\n".join(lines)
    html = "<pre style='font-family:sans-serif'>" + body.replace("\n", "<br>") + "</pre>"
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=settings.ADMIN_EMAIL,
            to_emails=settings.ADMIN_EMAIL,
            subject="IVY AI Counsellor - Weekly Gap Report",
            html_content=html,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
        return True
    except Exception as e:
        logger.warning("Gap report send failed: %s", e)
        return False


def schedule_gap_report(scheduler: AsyncIOScheduler) -> None:
    """Schedule every Monday 9:00 AM IST."""
    tz = ZoneInfo("Asia/Kolkata")

    def _run():
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(send_gap_report(7))
        except RuntimeError:
            asyncio.run(send_gap_report(7))

    scheduler.add_job(
        _run,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        timezone=tz,
    )
