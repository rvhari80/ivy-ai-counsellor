"""WhatsApp and email alerts for hot leads."""
import os
import asyncio
from datetime import datetime, timedelta
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import httpx

from app.models.schemas import IntentResult
from app.models.database import get_db, get_lead_by_session, set_lead_notified, upsert_lead

logger = logging.getLogger(__name__)

COUNSELLOR_WHATSAPP = os.getenv("COUNSELLOR_WHATSAPP", "")
COUNSELLOR_EMAIL = os.getenv("COUNSELLOR_EMAIL", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
META_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
PHONE_ID = os.getenv("META_PHONE_NUMBER_ID", "")
HOT_THRESHOLD = int(os.getenv("HOT_LEAD_THRESHOLD", "60"))
COOLDOWN_MIN = int(os.getenv("NOTIFICATION_COOLDOWN_MINUTES", "30"))


def _whatsapp_body(result: IntentResult, session_id: str) -> str:
    p = result.extracted_profile
    return (
        "HOT LEAD ALERT - IVY AI Counsellor\n\n"
        f"Name: {p.name or 'Unknown'}\n"
        f"Phone: {p.phone or 'Not provided'}\n"
        f"Course: {p.target_course or '-'} | Country: {p.target_country or '-'}\n"
        f"Intake: {p.target_intake or '-'} | Budget: {p.budget_inr or '-'}\n"
        f"IELTS: {p.ielts_score or '-'} | Percentage: {p.percentage or '-'}\n"
        f"Lead Score: {result.lead_score}/100\n\n"
        f"Summary: {result.conversation_summary}\n"
        f"Action: {result.recommended_action}"
    )


async def send_whatsapp_alert(to_number: str, body: str) -> bool:
    """Send plain text to WhatsApp (Meta Cloud API)."""
    if not META_TOKEN or not PHONE_ID:
        logger.warning("WhatsApp not configured")
        return False
    # Normalize number: remove + and spaces
    to = to_number.replace(" ", "").replace("+", "")
    if not to.startswith("91") and len(to) == 10:
        to = "91" + to
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "text",
        "text": {"body": body[:1000]},
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"},
                timeout=10.0,
            )
            if r.status_code >= 400:
                logger.warning("WhatsApp send failed: %s %s", r.status_code, r.text)
                return False
            return True
    except Exception as e:
        logger.warning("WhatsApp error: %s", e)
        return False


def _email_html(result: IntentResult, session_id: str) -> str:
    p = result.extracted_profile
    primary = "#1B5E20"
    accent = "#F9A825"
    rows = [
        ("Name", p.name or "-"),
        ("Phone", p.phone or "-"),
        ("Email", p.email or "-"),
        ("Course", p.target_course or "-"),
        ("Country", p.target_country or "-"),
        ("Intake", p.target_intake or "-"),
        ("Budget (INR)", str(p.budget_inr) if p.budget_inr else "-"),
        ("IELTS", p.ielts_score or "-"),
        ("Percentage", p.percentage or "-"),
        ("Lead Score", str(result.lead_score)),
        ("Intent", result.intent_level),
    ]
    trs = "".join(f"<tr><td style='padding:6px;border:1px solid #ccc'>{k}</td><td style='padding:6px;border:1px solid #ccc'>{v}</td></tr>" for k, v in rows)
    return f"""
    <div style="font-family:sans-serif; max-width:600px;">
      <h2 style="color:{primary}">HOT LEAD ALERT - IVY AI Counsellor</h2>
      <p><strong>Session:</strong> {session_id}</p>
      <table style="border-collapse:collapse;">{trs}</table>
      <p><strong>Summary:</strong> {result.conversation_summary}</p>
      <p><strong>Recommended action:</strong> {result.recommended_action}</p>
      <p style="color:{primary}; margin-top:24px;">IVY Overseas</p>
    </div>
    """


async def send_email_alert(to_email: str, subject: str, html: str) -> bool:
    if not SENDGRID_KEY:
        logger.warning("SendGrid not configured")
        return False
    try:
        message = Mail(
            from_email=ADMIN_EMAIL or "noreply@ivyoverseas.com",
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        sg = SendGridAPIClient(SENDGRID_KEY)
        sg.send(message)
        return True
    except Exception as e:
        logger.warning("SendGrid error: %s", e)
        return False


async def should_skip_notification(session_id: str) -> bool:
    """True if we already notified this session within cooldown."""
    async with get_db() as conn:
        row = await get_lead_by_session(conn, session_id)
    if not row:
        return False
    notified_at = row[15] if len(row) > 15 else None  # notified_at column
    if not notified_at:
        return False
    try:
        dt = datetime.fromisoformat(notified_at.replace("Z", "+00:00"))
    except Exception:
        return False
    if datetime.now(dt.tzinfo) - dt < timedelta(minutes=COOLDOWN_MIN):
        return True
    return False


async def notify_hot_lead(session_id: str, result: IntentResult) -> None:
    """Upsert lead, then send WhatsApp + email concurrently if score >= threshold and not in cooldown."""
    if result.lead_score < HOT_THRESHOLD:
        return
    p = result.extracted_profile
    async with get_db() as conn:
        await upsert_lead(
            conn,
            session_id=session_id,
            name=p.name,
            phone=p.phone,
            email=p.email,
            target_course=p.target_course,
            target_country=p.target_country,
            target_intake=p.target_intake,
            budget_inr=p.budget_inr,
            ielts_score=p.ielts_score,
            percentage=p.percentage,
            lead_score=result.lead_score,
            intent_level=result.intent_level,
            conversation_summary=result.conversation_summary,
            recommended_action=result.recommended_action,
            notified_at=None,
        )
    if await should_skip_notification(session_id):
        return
    body = _whatsapp_body(result, session_id)
    html = _email_html(result, session_id)
    await asyncio.gather(
        send_whatsapp_alert(COUNSELLOR_WHATSAPP, body),
        send_email_alert(COUNSELLOR_EMAIL, "HOT LEAD - IVY AI Counsellor", html),
    )
    now = datetime.utcnow().isoformat() + "Z"
    async with get_db() as conn:
        await set_lead_notified(conn, session_id, now)
