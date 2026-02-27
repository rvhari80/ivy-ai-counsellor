"""Conversation memory manager with sliding window, summarization, and auto-expiry."""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from anthropic import Anthropic

logger = logging.getLogger(__name__)

MAX_PAIRS = 10  # Keep last 10 message pairs (20 messages total)
IDLE_EXPIRE_SECONDS = 30 * 60  # 30 minutes

# In-process store: session_id -> { "messages": [...], "last_activity": timestamp, "summary": str }
_sessions: dict[str, dict[str, Any]] = {}


class ConversationMemoryManager:
    """Manages conversation history with sliding window and summarization."""
    
    def __init__(self, anthropic_api_key: Optional[str] = None):
        """Initialize the memory manager.
        
        Args:
            anthropic_api_key: API key for Claude. If None, reads from ANTHROPIC_API_KEY env var.
        """
        self.api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("No Anthropic API key provided. Summarization will be disabled.")
    
    def _ensure_session(self, session_id: str) -> dict:
        """Ensure session exists and update last activity timestamp."""
        if session_id not in _sessions:
            _sessions[session_id] = {
                "messages": [],
                "last_activity": time.time(),
                "summary": None
            }
        _sessions[session_id]["last_activity"] = time.time()
        return _sessions[session_id]
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a new message to the conversation.
        
        Args:
            session_id: Unique session identifier
            role: Either 'user' or 'assistant'
            content: Message content
        """
        data = self._ensure_session(session_id)
        
        # Add message with timestamp
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now()
        }
        data["messages"].append(message)
        
        # Check if we need to apply sliding window
        self._apply_sliding_window(session_id)
    
    def _apply_sliding_window(self, session_id: str) -> None:
        """Apply sliding window logic: keep last 10 pairs, summarize older messages."""
        data = _sessions[session_id]
        messages = data["messages"]
        
        # Count message pairs (user + assistant = 1 pair)
        # We need to count complete pairs
        pair_count = 0
        for i in range(len(messages) - 1):
            if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
                pair_count += 1
        
        # If we have more than MAX_PAIRS, summarize older messages
        if pair_count > MAX_PAIRS:
            # Find the split point: keep last MAX_PAIRS pairs (20 messages)
            # We need to find where the last 10 pairs start
            pairs_to_keep = MAX_PAIRS
            messages_to_keep_count = pairs_to_keep * 2
            
            # Split messages
            old_messages = messages[:-messages_to_keep_count]
            recent_messages = messages[-messages_to_keep_count:]
            
            # Summarize old messages if we have a client
            if old_messages and self.client:
                summary = self._summarize_conversation(old_messages)
                data["summary"] = summary
                logger.info(f"Summarized {len(old_messages)} old messages for session {session_id}")
            
            # Keep only recent messages
            data["messages"] = recent_messages
    
    def _summarize_conversation(self, messages: list[dict]) -> str:
        """Summarize a list of messages using Claude API.
        
        Args:
            messages: List of message dictionaries to summarize
            
        Returns:
            Summary string
        """
        if not self.client:
            return "Previous conversation context (summarization unavailable)"
        
        # Format messages for summarization
        conversation_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in messages
        ])
        
        prompt = f"""Summarize this conversation in 3 sentences, preserving key student details like scores, country interest, course preferences, and budget.

Conversation:
{conversation_text}

Summary:"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response.content[0].text.strip()
            return summary
        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return "Previous conversation context (summarization failed)"
    
    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Get formatted message history for Claude API.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of messages formatted for Claude API (role and content only)
        """
        data = self._ensure_session(session_id)
        result = []
        
        # Add summary as a system-like message if it exists
        if data.get("summary"):
            result.append({
                "role": "user",
                "content": f"[Previous conversation summary: {data['summary']}]"
            })
        
        # Add recent messages (without timestamp for API compatibility)
        for msg in data["messages"]:
            result.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        return result
    
    def clear_session(self, session_id: str) -> None:
        """Remove session data.
        
        Args:
            session_id: Unique session identifier
        """
        if session_id in _sessions:
            del _sessions[session_id]
            logger.info(f"Cleared session: {session_id}")
    
    def expire_idle_sessions(self) -> int:
        """Remove sessions that have been inactive for more than 30 minutes.
        
        Returns:
            Number of sessions expired
        """
        now = time.time()
        to_delete = [
            sid for sid, data in _sessions.items()
            if now - data["last_activity"] > IDLE_EXPIRE_SECONDS
        ]
        
        for sid in to_delete:
            del _sessions[sid]
        
        if to_delete:
            logger.info(f"Expired {len(to_delete)} idle sessions")
        
        return len(to_delete)
    
    def get_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(_sessions)
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get session information for debugging/testing.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Session data or None if session doesn't exist
        """
        return _sessions.get(session_id)


# Global instance for easy access
_manager: Optional[ConversationMemoryManager] = None


def get_memory_manager() -> ConversationMemoryManager:
    """Get or create the global memory manager instance."""
    global _manager
    if _manager is None:
        _manager = ConversationMemoryManager()
    return _manager


# Convenience functions for backward compatibility
def add_message(session_id: str, role: str, content: str) -> None:
    """Add a message to the conversation."""
    get_memory_manager().add_message(session_id, role, content)


def get_history(session_id: str) -> list[dict[str, str]]:
    """Get formatted message history for Claude API."""
    return get_memory_manager().get_history(session_id)


def clear_session(session_id: str) -> None:
    """Remove session data."""
    get_memory_manager().clear_session(session_id)


def expire_idle_sessions() -> int:
    """Remove idle sessions and return count of expired sessions."""
    return get_memory_manager().expire_idle_sessions()
