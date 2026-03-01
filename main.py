"""
IVY AI Counsellor - FastAPI application entry point.

This is the main application file that initializes FastAPI, sets up middleware,
includes routers, and handles application lifecycle events.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from app.models.database import init_db
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.services.gap_report_service import schedule_gap_report
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Scheduler (global so it can be stopped on shutdown) ───────────────────────
scheduler = AsyncIOScheduler()


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""

    # ── STARTUP ──────────────────────────────────────────────
    logger.info("Starting IVY AI Counsellor...")
    logger.info("Environment : %s", os.getenv("ENVIRONMENT", "development"))
    logger.info("OpenAI model: %s", os.getenv("OPENAI_MODEL", "gpt-4o"))
    logger.info("Pinecone idx: %s", os.getenv("PINECONE_INDEX", "ivy-counsellor"))

    # 1. Database
    try:
        await init_db()
        logger.info("Database initialised ✅")
    except Exception as e:
        logger.error("Database init failed: %s", e)
        raise

    # 2. APScheduler — weekly gap report every Monday 9 AM IST
    try:
        schedule_gap_report(scheduler)
        scheduler.start()
        logger.info("Scheduler started ✅")
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)

    logger.info("Application startup complete ✅")

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────
    logger.info("Shutting down IVY AI Counsellor...")
    try:
        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped ✅")
    except Exception as e:
        logger.warning("Scheduler shutdown error: %s", e)

    logger.info("Shutdown complete.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "IVY AI Counsellor",
    description = "RAG-based AI chat agent for IVY Overseas study abroad counselling",
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────


app.add_middleware(
    CORSMiddleware,
    allow_origins     = [o.strip() for o in os.getenv(
                            "ALLOWED_ORIGINS",
                            "http://localhost:3000,http://localhost:8000"
                         ).split(",")],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Static files (admin dashboard) ───────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    logger.info("Static files mounted at /static")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat_router,  prefix="/api/v1",       tags=["chat"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


# ── Core endpoints ────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root():
    """API information."""
    return {
        "name":        "IVY AI Counsellor API",
        "version":     "1.0.0",
        "status":      "operational",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "docs":        "/docs",
        "health":      "/api/v1/health",
        "admin":       "/static/admin.html",
    }


@app.get("/api/v1/health", tags=["root"])
async def health():
    """Health check — used by Railway as readiness probe."""
    return {
        "status":      "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "scheduler":   "running" if scheduler.running else "stopped",
    }


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host      = "0.0.0.0",
        port      = int(os.getenv("PORT", 8000)),
        reload    = True,
        log_level = "info",
    )