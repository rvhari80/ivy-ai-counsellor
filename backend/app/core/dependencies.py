"""
FastAPI dependencies for dependency injection.
"""
from typing import AsyncGenerator
import aiosqlite
from app.config.settings import settings


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Database connection dependency.
    Provides an async SQLite connection that is automatically closed after use.

    Usage:
        @app.get("/example")
        async def example(db: aiosqlite.Connection = Depends(get_db)):
            async with db.execute("SELECT * FROM table") as cursor:
                result = await cursor.fetchall()

    Yields:
        aiosqlite.Connection: Database connection
    """
    # Extract just the path from the database URL
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")

    async with aiosqlite.connect(db_path) as db:
        # Enable row factory for dict-like access
        db.row_factory = aiosqlite.Row
        yield db


async def get_settings():
    """
    Settings dependency.
    Provides access to application settings.

    Usage:
        @app.get("/config")
        async def get_config(settings: Settings = Depends(get_settings)):
            return {"model": settings.ANTHROPIC_MODEL}

    Returns:
        Settings: Application settings
    """
    return settings
