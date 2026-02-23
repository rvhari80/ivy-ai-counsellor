"""
IVY AI Counsellor - FastAPI application entry point.

This is the main application file that initializes FastAPI, sets up middleware,
includes routers, and handles application lifecycle events.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
import logging

from app.config.settings import settings
from app.config.logging import setup_logging
from app.config.constants import API_VERSION
from app.core.middleware import setup_middleware
from app.models.database import init_db
from app.routes.api import api_router


# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting IVY AI Counsellor application...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Model: {settings.ANTHROPIC_MODEL}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down IVY AI Counsellor application...")


# Create FastAPI app instance
app = FastAPI(
    title="IVY AI Counsellor",
    description="RAG-based AI chat agent for IVY Overseas study abroad counseling",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Setup middleware (CORS, logging, error handling)
setup_middleware(app)

# Include API routes under /api/v1
app.include_router(api_router, prefix=f"/api/{API_VERSION}")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "IVY AI Counsellor API",
        "version": API_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "operational",
    }


# Health check endpoint (also available at /api/v1/health)
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": API_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
