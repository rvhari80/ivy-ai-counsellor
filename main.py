"""
IVY AI Counsellor - FastAPI application entry point.

This is the main application file that initializes FastAPI, sets up middleware,
includes routers, and handles application lifecycle events.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.models.database import init_db
from app.routes.chat import router as chat_router

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting IVY AI Counsellor application...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Model: {os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5')}")

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
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "message": "IVY AI Counsellor API",
        "version": "1.0.0",
        "status": "operational",
    }


# Health check endpoint
@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
