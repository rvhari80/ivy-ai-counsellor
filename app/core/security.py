"""
Security utilities including rate limiting and authentication.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config.settings import settings

# Rate limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
)


def get_rate_limiter():
    """
    Get rate limiter instance for dependency injection.

    Usage:
        @app.post("/api/chat")
        @limiter.limit("10/minute")
        async def chat(request: Request):
            pass
    """
    return limiter
