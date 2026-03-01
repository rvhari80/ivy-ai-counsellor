"""
Gap Report Service for IVY AI Counsellor.

Generates and sends weekly HTML email reports of unanswered student queries.
Helps counsellors identify knowledge gaps and prioritise PDF updates.

Schedule: Every Monday 9:00 AM IST
Manual:   GET /admin/gap-report
"""

import os
import re
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite

from app.models.database import DB_PATH

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
ADMIN_EMAIL    = os.getenv("ADMIN_EMAIL", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", "ai@ivyoverseas.com")
SMTP2GO_KEY    = os.getenv("SMTP2GO_API_KEY", "")
ADMIN_DASH_URL = os.getenv("ADMIN_DASHBOARD_URL", "http://localhost:8000/static/admin.html")
IST            = ZoneInfo("Asia/Kolkata")

# ── Keyword clusters for grouping similar queries ─────────────────────────────
TOPIC_CLUSTERS = {
    "IELTS / PTE":        ["ielts", "pte", "english test", "band score", "listening", "speaking", "writing score"],
    "Australia Visa":     ["australia", "subclass 500", "oshc", "aus visa", "australian"],
    "Canada Visa":        ["canada", "ircc", "study permit", "canadian"],
    "UK Visa":            ["uk", "united kingdom", "tier 4", "cas number", "british"],
    "USA Visa":           ["usa", "united states", "f-1", "f1 visa", "sevis", "american"],
    "Germany Visa":       ["germany", "german", "blocked account", "APS"],
    "Scholarships":       ["scholarship", "grant", "funding", "bursary", "stipend", "fellowship"],
    "SOP / LOR":          ["sop", "statement of purpose", "lor", "recommendation", "personal statement"],
    "University Ranking": ["ranking", "qs rank", "top university", "best university", "university list"],
    "Tuition Fees":       ["fee", "tuition", "cost", "afford", "expensive", "budget", "lakhs"],
    "Post Study Work":    ["post study", "work visa", "pr", "permanent resident", "after studies", "485"],
    "Accommodation":      ["accommodation", "housing", "hostel", "rent", "staying", "where to live"],
    "Part Time Work":     ["part time", "work while", "hours", "earn", "job during"],
    "Application":        ["application", "apply", "deadline", "portal", "ucas", "common app"],
    "GPA / Percentage":   ["gpa", "percentage", "marks", "grade", "aggregate", "cgpa"],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Query SQLite for unanswered queries
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_unanswered_queries(days: int = 7) -> list[dict]:
    """
    Fetch all unanswered queries from last N days.
    Returns list of dicts with query_text, fallback_type, score, timestamp.
    """
    since = (datetime.now(IST) - timedelta(days=days)).strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, query_text, fallback_type, best_score, session_id,
                      timestamp, notified
               FROM unanswered_queries
               WHERE date(timestamp) >= date(?)
                 AND (notified IS NULL OR notified = 0)
               ORDER BY timestamp DESC""",
            (since,)
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Group similar queries by keyword matching
# ═══════════════════════════════════════════════════════════════════════════════

def normalise(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def assign_topic(query: str) -> str:
    """
    Assign a topic cluster to a query using keyword matching.
    Returns topic name or 'Other' if no match found.
    """
    q = normalise(query)
    for topic, keywords in TOPIC_CLUSTERS.items():
        if any(kw in q for kw in keywords):
            return topic
    return "Other"


def group_queries(queries: list[dict]) -> dict[str, list[dict]]:
    """
    Group raw queries by topic cluster.

    Returns:
        dict mapping topic_name -> list of query dicts
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for q in queries:
        topic = assign_topic(q["query_text"])
        groups[topic].append(q)
    return dict(groups)


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — Rank by frequency and build top-10 summary
# ═══════════════════════════════════════════════════════════════════════════════

def rank_topics(groups: dict[str, list[dict]]) -> list[dict]:
    """
    Rank topic groups by frequency (most asked first).

    Returns list of dicts:
        topic, count, fallback_types, sample_queries, avg_score
    """
    ranked = []
    for topic, queries in groups.items():
        # Count fallback types
        fallback_counts: dict[str, int] = defaultdict(int)
        for q in queries:
            ft = q.get("fallback_type") or "UNKNOWN"
            fallback_counts[ft] += 1

        # Get avg similarity score
        scores = [q.get("best_score") or 0 for q in queries]
        avg_score = round(sum(scores) / len(scores), 3) if scores else 0

        # Get 3 representative sample queries (shortest = most specific)
        samples = sorted(
            [q["query_text"] for q in queries],
            key=len
        )[:3]

        ranked.append({
            "topic":          topic,
            "count":          len(queries),
            "fallback_types": dict(fallback_counts),
            "sample_queries": samples,
            "avg_score":      avg_score,
            "query_ids":      [q["id"] for q in queries],
        })

    # Sort by frequency descending
    ranked.sort(key=lambda x: x["count"], reverse=True)
    return ranked[:10]  # top 10 only


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Generate HTML email
# ═══════════════════════════════════════════════════════════════════════════════

def build_email_html(
    ranked_topics: list[dict],
    total_queries:  int,
    unique_topics:  int,
    top_category:   str,
    report_date:    str,
    days:           int,
) -> tuple[str, str]:
    """
    Build subject line and HTML email body.

    Returns:
        (subject, html_body)
    """
    subject = (
        f"IVY AI Weekly Gap Report — {report_date} — "
        f"{unique_topics} Topics Need PDF Updates"
    )

    # ── Colour palette ────────────────────────────────────────
    GREEN      = "#1B5E20"
    GREEN_LIGHT= "#E8F5E9"
    GREEN_MID  = "#388E3C"
    GOLD       = "#F9A825"
    GOLD_LIGHT = "#FFF8E1"
    GOLD_DARK  = "#F57F17"
    WHITE      = "#FFFFFF"
    GREY_BG    = "#F5F5F5"
    GREY_TEXT  = "#616161"
    DARK_TEXT  = "#1A1A1A"
    BORDER     = "#E0E0E0"

    # ── Table rows ─────────────────────────────────────────────
    table_rows = ""
    for i, t in enumerate(ranked_topics, 1):
        # Severity colour based on frequency
        if t["count"] >= 10:
            count_bg, count_color = "#FFEBEE", "#C62828"
        elif t["count"] >= 5:
            count_bg, count_color = GOLD_LIGHT, GOLD_DARK
        else:
            count_bg, count_color = GREEN_LIGHT, GREEN_DARK = GREEN_LIGHT, GREEN_MID

        # Sample queries list
        samples_html = "".join(
            f'<li style="margin:3px 0;color:{GREY_TEXT};font-size:12px">{q[:120]}</li>'
            for q in t["sample_queries"]
        )

        # Fallback type tags
        ft_tags = "".join(
            f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
            f'font-size:10px;font-weight:700;margin:2px;'
            f'background:{GREY_BG};color:{GREY_TEXT}">'
            f'{ft} ×{cnt}</span>'
            for ft, cnt in t["fallback_types"].items()
        )

        row_bg = WHITE if i % 2 == 0 else GREY_BG

        table_rows += f"""
        <tr style="background:{row_bg}">
          <td style="padding:14px 12px;text-align:center;font-weight:700;
                     color:{GREY_TEXT};font-size:15px;border-bottom:1px solid {BORDER}">
            #{i}
          </td>
          <td style="padding:14px 12px;border-bottom:1px solid {BORDER}">
            <div style="font-weight:700;color:{DARK_TEXT};font-size:14px;
                        margin-bottom:4px">{t["topic"]}</div>
            <ul style="margin:6px 0 4px 16px;padding:0">{samples_html}</ul>
            <div style="margin-top:6px">{ft_tags}</div>
          </td>
          <td style="padding:14px 12px;text-align:center;border-bottom:1px solid {BORDER}">
            <span style="display:inline-block;padding:6px 14px;border-radius:20px;
                         font-size:18px;font-weight:800;
                         background:{count_bg};color:{count_color}">
              {t["count"]}
            </span>
            <div style="font-size:10px;color:{GREY_TEXT};margin-top:3px">times asked</div>
          </td>
          <td style="padding:14px 12px;text-align:center;border-bottom:1px solid {BORDER};
                     color:{GREY_TEXT};font-size:12px">
            {t["avg_score"]:.2f}<br>
            <span style="font-size:10px">avg match</span>
          </td>
        </tr>
        """

    # ── PDF action items ───────────────────────────────────────
    pdf_actions = ""
    for i, t in enumerate(ranked_topics[:5], 1):
        pdf_actions += f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid {BORDER}">
            <span style="font-weight:700;color:{GREEN}">{i}.</span>
            Create or update PDF for <strong>{t["topic"]}</strong>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid {BORDER};
                     color:{GREY_TEXT};font-size:12px">
            {t["count"]} students affected
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid {BORDER}">
            <span style="background:{GOLD_LIGHT};color:{GOLD_DARK};padding:3px 10px;
                         border-radius:12px;font-size:11px;font-weight:700">
              HIGH PRIORITY
            </span>
          </td>
        </tr>
        """

    # ── Full HTML ──────────────────────────────────────────────
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IVY AI Weekly Gap Report</title>
</head>
<body style="margin:0;padding:0;background:{GREY_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">

<table width="100%" cellpadding="0" cellspacing="0" style="background:{GREY_BG}">
<tr><td align="center" style="padding:32px 16px">

  <table width="620" cellpadding="0" cellspacing="0"
         style="max-width:620px;width:100%;background:{WHITE};border-radius:12px;
                overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.10)">

    <!-- ── HEADER ── -->
    <tr>
      <td style="background:linear-gradient(135deg,{GREEN},{GREEN_MID});padding:28px 32px">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="font-size:13px;color:rgba(255,255,255,0.7);
                          letter-spacing:2px;text-transform:uppercase;margin-bottom:6px">
                IVY OVERSEAS AI COUNSELLOR
              </div>
              <h1 style="margin:0;color:{WHITE};font-size:24px;font-weight:800">
                📊 Weekly Gap Report
              </h1>
              <div style="color:rgba(255,255,255,0.85);font-size:13px;margin-top:6px">
                {report_date} · Last {days} days · Auto-generated every Monday 9:00 AM IST
              </div>
            </td>
            <td align="right" style="vertical-align:top">
              <div style="background:{GOLD};color:{GREEN};padding:8px 16px;border-radius:20px;
                          font-weight:800;font-size:14px;white-space:nowrap">
                {unique_topics} Topics
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ── SUMMARY STATS ── -->
    <tr>
      <td style="padding:24px 32px;background:{GREEN_LIGHT};border-bottom:3px solid {GOLD}">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td align="center" width="33%">
              <div style="font-size:36px;font-weight:800;color:{GREEN}">{total_queries}</div>
              <div style="font-size:12px;color:{GREY_TEXT};margin-top:2px">Total Unanswered</div>
            </td>
            <td align="center" width="33%"
                style="border-left:1px solid {BORDER};border-right:1px solid {BORDER}">
              <div style="font-size:36px;font-weight:800;color:{GREEN_MID}">{unique_topics}</div>
              <div style="font-size:12px;color:{GREY_TEXT};margin-top:2px">Unique Topics</div>
            </td>
            <td align="center" width="33%">
              <div style="font-size:18px;font-weight:800;color:{GOLD_DARK};line-height:1.2">
                {top_category}
              </div>
              <div style="font-size:12px;color:{GREY_TEXT};margin-top:2px">Top Gap Category</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- ── TOP 10 TABLE ── -->
    <tr>
      <td style="padding:28px 32px 0">
        <h2 style="margin:0 0 16px;font-size:18px;color:{GREEN};
                   display:flex;align-items:center;gap:8px">
          🔍 Top {len(ranked_topics)} Unanswered Topics
        </h2>

        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid {BORDER};border-radius:8px;overflow:hidden">
          <thead>
            <tr style="background:{GREEN}">
              <th style="padding:12px;color:{WHITE};font-size:12px;width:40px">#</th>
              <th style="padding:12px;color:{WHITE};font-size:12px;text-align:left">
                Topic & Sample Questions
              </th>
              <th style="padding:12px;color:{WHITE};font-size:12px;width:80px">Asked</th>
              <th style="padding:12px;color:{WHITE};font-size:12px;width:80px">
                Avg Match
              </th>
            </tr>
          </thead>
          <tbody>
            {table_rows}
          </tbody>
        </table>
      </td>
    </tr>

    <!-- ── ACTION REQUIRED ── -->
    <tr>
      <td style="padding:28px 32px 0">
        <div style="background:{GOLD_LIGHT};border:2px solid {GOLD};
                    border-radius:10px;padding:20px">
          <h3 style="margin:0 0 14px;color:{GOLD_DARK};font-size:16px">
            ⚡ Action Required — Please Update These PDFs
          </h3>
          <table width="100%" cellpadding="0" cellspacing="0">
            <thead>
              <tr style="background:rgba(249,168,37,0.2)">
                <th style="padding:8px 14px;text-align:left;font-size:12px;
                           color:{GOLD_DARK}">PDF to Create/Update</th>
                <th style="padding:8px 14px;font-size:12px;color:{GOLD_DARK}">Impact</th>
                <th style="padding:8px 14px;font-size:12px;color:{GOLD_DARK}">Priority</th>
              </tr>
            </thead>
            <tbody>
              {pdf_actions}
            </tbody>
          </table>
          <p style="margin:14px 0 0;font-size:12px;color:{GREY_TEXT}">
            After updating PDFs, use the Admin Dashboard to re-ingest them into Pinecone.
            This will improve AI accuracy for these topics immediately.
          </p>
        </div>
      </td>
    </tr>

    <!-- ── HOW TO FIX ── -->
    <tr>
      <td style="padding:24px 32px 0">
        <div style="background:{GREY_BG};border-radius:8px;padding:18px">
          <h3 style="margin:0 0 10px;font-size:14px;color:{DARK_TEXT}">
            📋 How to Add Missing Content
          </h3>
          <ol style="margin:0;padding-left:18px;color:{GREY_TEXT};
                     font-size:13px;line-height:1.8">
            <li>Write a Q&A style PDF covering the missing topic</li>
            <li>Open the Admin Dashboard (link below)</li>
            <li>Upload PDF with correct Category and Country tags</li>
            <li>IVY AI will answer these questions from the next student onwards</li>
          </ol>
        </div>
      </td>
    </tr>

    <!-- ── CTA BUTTON ── -->
    <tr>
      <td style="padding:28px 32px" align="center">
        <a href="{ADMIN_DASH_URL}"
           style="display:inline-block;background:linear-gradient(135deg,{GREEN},{GREEN_MID});
                  color:{WHITE};padding:14px 36px;border-radius:25px;font-weight:700;
                  font-size:15px;text-decoration:none;
                  box-shadow:0 4px 16px rgba(27,94,32,0.35)">
          📤 Open Admin Dashboard — Upload PDFs
        </a>
      </td>
    </tr>

    <!-- ── FOOTER ── -->
    <tr>
      <td style="background:{GREEN};padding:18px 32px">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="color:rgba(255,255,255,0.9);font-size:12px">
                IVY Overseas AI Counsellor · Auto-generated report<br>
                <span style="opacity:0.6">
                  This email is sent every Monday at 9:00 AM IST.
                  Queries are marked as notified after this email.
                </span>
              </div>
            </td>
            <td align="right">
              <a href="{ADMIN_DASH_URL}"
                 style="color:{GOLD};font-size:12px;text-decoration:none;font-weight:600">
                Admin Dashboard →
              </a>
            </td>
          </tr>
        </table>
      </td>
    </tr>

  </table><!-- end email table -->

</td></tr>
</table><!-- end outer table -->

</body>
</html>
"""
    return subject, html


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 5 — Send via SMTP2GO
# ═══════════════════════════════════════════════════════════════════════════════

async def send_via_smtp2go(subject: str, html_body: str) -> bool:
    """Send HTML email via SMTP2GO REST API."""
    if not SMTP2GO_KEY:
        logger.warning("Gap report: SMTP2GO_API_KEY not set")
        return False
    if not ADMIN_EMAIL:
        logger.warning("Gap report: ADMIN_EMAIL not set")
        return False

    payload = {
        "api_key":   SMTP2GO_KEY,
        "to":        [ADMIN_EMAIL],
        "sender":    EMAIL_FROM,
        "subject":   subject,
        "html_body": html_body,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.smtp2go.com/v3/email/send",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json()
                succeeded = result.get("data", {}).get("succeeded", 0)
                if succeeded == 1:
                    logger.info("Gap report sent to %s", ADMIN_EMAIL)
                    return True
                else:
                    logger.warning("SMTP2GO send failed: %s", result)
                    return False
    except Exception as e:
        logger.error("Gap report send error: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 6 — Mark queries as NOTIFIED in database
# ═══════════════════════════════════════════════════════════════════════════════

async def mark_as_notified(query_ids: list[int]) -> None:
    """Mark all reported queries as notified so they are not re-reported."""
    if not query_ids:
        return
    placeholders = ",".join("?" * len(query_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE unanswered_queries SET notified = 1 WHERE id IN ({placeholders})",
            query_ids
        )
        await db.commit()
    logger.info("Marked %d queries as notified", len(query_ids))


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_and_send_gap_report(days: int = 7) -> dict:
    """
    Full pipeline:
    1. Fetch unanswered queries from SQLite
    2. Group by topic using keyword matching
    3. Rank by frequency
    4. Build HTML email
    5. Send via SMTP2GO
    6. Mark as notified in DB

    Returns summary dict (used by admin API endpoint).
    """
    now = datetime.now(IST)
    report_date = now.strftime("%d %b %Y")

    logger.info("Starting gap report generation for last %d days", days)

    # Step 1 — Fetch
    queries = await fetch_unanswered_queries(days=days)
    total_queries = len(queries)

    if total_queries == 0:
        logger.info("Gap report: no unanswered queries in last %d days", days)
        return {
            "success": True,
            "sent": False,
            "reason": "No unanswered queries found",
            "total_queries": 0,
            "unique_topics": 0,
        }

    # Step 2 — Group
    groups = group_queries(queries)

    # Step 3 — Rank
    ranked = rank_topics(groups)
    unique_topics = len(groups)
    top_category = ranked[0]["topic"] if ranked else "N/A"

    # Step 4 — Build email
    subject, html = build_email_html(
        ranked_topics  = ranked,
        total_queries  = total_queries,
        unique_topics  = unique_topics,
        top_category   = top_category,
        report_date    = report_date,
        days           = days,
    )

    # Step 5 — Send
    sent = await send_via_smtp2go(subject, html)

    # Step 6 — Mark notified (only if email sent successfully)
    all_ids = [q["id"] for q in queries]
    if sent:
        await mark_as_notified(all_ids)

    result = {
        "success":       True,
        "sent":          sent,
        "report_date":   report_date,
        "period_days":   days,
        "total_queries": total_queries,
        "unique_topics": unique_topics,
        "top_category":  top_category,
        "email_to":      ADMIN_EMAIL,
        "top_10": [
            {
                "rank":           i + 1,
                "topic":          t["topic"],
                "count":          t["count"],
                "sample_queries": t["sample_queries"],
                "avg_score":      t["avg_score"],
            }
            for i, t in enumerate(ranked)
        ],
    }

    logger.info(
        "Gap report complete: %d queries, %d topics, sent=%s",
        total_queries, unique_topics, sent
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  STEP 7 — APScheduler — every Monday 9:00 AM IST
# ═══════════════════════════════════════════════════════════════════════════════

def schedule_gap_report(scheduler: AsyncIOScheduler) -> None:
    """Register weekly gap report job with APScheduler."""

    def _run():
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(generate_and_send_gap_report(days=7))
        except RuntimeError:
            asyncio.run(generate_and_send_gap_report(days=7))

    scheduler.add_job(
        _run,
        trigger   = "cron",
        day_of_week = "mon",
        hour      = 9,
        minute    = 0,
        timezone  = IST,
        id        = "weekly_gap_report",
        replace_existing = True,
    )
    logger.info("Gap report scheduled: every Monday 9:00 AM IST")
