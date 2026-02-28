"""Chat endpoint for IVY AI Counsellor."""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator

from app.services.rag_service import query_rag
from app.models.database import get_db, save_conversation

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory rate limiting per session (30 messages per hour)
_session_message_counts: dict[str, list[datetime]] = {}
MAX_MESSAGES_PER_HOUR = 30


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str = Field(..., min_length=1, max_length=100, description="Unique session identifier")
    message: str = Field(..., min_length=1, max_length=500, description="User message")
    metadata: Optional[dict] = Field(default=None, description="Optional metadata")

    @validator('message')
    def validate_message(cls, v):
        """Validate message is not empty after stripping whitespace."""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


def check_session_rate_limit(session_id: str) -> bool:
    """
    Check if session has exceeded rate limit of 30 messages per hour.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if rate limit exceeded, False otherwise
    """
    now = datetime.utcnow()
    
    # Initialize session if not exists
    if session_id not in _session_message_counts:
        _session_message_counts[session_id] = []
    
    # Remove timestamps older than 1 hour
    one_hour_ago = datetime.utcnow().timestamp() - 3600
    _session_message_counts[session_id] = [
        ts for ts in _session_message_counts[session_id]
        if ts.timestamp() > one_hour_ago
    ]
    
    # Check if limit exceeded
    if len(_session_message_counts[session_id]) >= MAX_MESSAGES_PER_HOUR:
        return True
    
    # Add current timestamp
    _session_message_counts[session_id].append(now)
    return False


async def generate_sse_stream(session_id: str, message: str):
    """
    Generate Server-Sent Events stream for chat response.
    
    Args:
        session_id: Session identifier
        message: User message
        
    Yields:
        Formatted SSE chunks
    """
    full_response = ""
    
    try:
        # Stream tokens from RAG service
        async for token in query_rag(message, session_id):
            full_response += token
            
            # Format as SSE with JSON payload
            chunk_data = {
                "token": token,
                "done": False
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
        
        # Send final chunk
        final_data = {
            "token": "",
            "done": True,
            "session_id": session_id
        }
        yield f"data: {json.dumps(final_data)}\n\n"
        
        # Log conversation to SQLite
        try:
            async with get_db() as conn:
                await save_conversation(
                    conn=conn,
                    session_id=session_id,
                    user_message=message,
                    ai_response=full_response,
                    platform="web"
                )
            logger.info(f"Logged conversation for session {session_id}")
        except Exception as db_error:
            logger.error(f"Failed to log conversation: {db_error}", exc_info=True)
            # Don't fail the request if logging fails
            
    except Exception as e:
        logger.error(f"Error in chat stream: {e}", exc_info=True)
        
        # Send generic error message to user (never expose internal errors)
        error_data = {
            "token": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment or contact our support team for assistance.",
            "done": False
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        
        # Send final chunk
        final_data = {
            "token": "",
            "done": True,
            "session_id": session_id
        }
        yield f"data: {json.dumps(final_data)}\n\n"


@router.post("/chat")
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    """
    Streaming chat endpoint with RAG integration.
    
    Features:
    - Input validation (max 500 chars, no empty messages)
    - Rate limiting (30 messages per session per hour)
    - Streaming response via Server-Sent Events
    - SQLite conversation logging
    - Graceful error handling
    
    Args:
        request: FastAPI request object
        chat_request: Chat request with session_id, message, and optional metadata
        
    Returns:
        StreamingResponse with text/event-stream content type
        
    Raises:
        HTTPException: 429 if rate limited, 422 if validation fails
    """
    try:
        # Check rate limit
        if check_session_rate_limit(chat_request.session_id):
            logger.warning(f"Rate limit exceeded for session {chat_request.session_id}")
            raise HTTPException(
                status_code=429,
                detail="Please wait before sending another message"
            )
        
        # Log request
        logger.info(
            f"Chat request - session: {chat_request.session_id}, "
            f"message length: {len(chat_request.message)}"
        )
        
        # Return streaming response
        return StreamingResponse(
            generate_sse_stream(chat_request.session_id, chat_request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 429)
        raise
    except Exception as e:
        # Log error but return generic message to user
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again later."
        )
