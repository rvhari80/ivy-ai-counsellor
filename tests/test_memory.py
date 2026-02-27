"""Unit tests for conversation memory manager."""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.utils.memory import (
    ConversationMemoryManager,
    _sessions,
    MAX_PAIRS,
    IDLE_EXPIRE_SECONDS
)


@pytest.fixture
def memory_manager():
    """Create a fresh memory manager for each test."""
    # Clear global sessions
    _sessions.clear()
    # Create manager without API key (to avoid real API calls in most tests)
    return ConversationMemoryManager(anthropic_api_key=None)


@pytest.fixture
def memory_manager_with_mock_client():
    """Create a memory manager with a mocked Anthropic client."""
    _sessions.clear()
    manager = ConversationMemoryManager(anthropic_api_key="test-key")
    
    # Mock the client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Student interested in Computer Science in USA with budget $50k and GPA 3.5. Discussed university options. Provided information about scholarships.")]
    mock_client.messages.create.return_value = mock_response
    manager.client = mock_client
    
    return manager


class TestBasicFunctionality:
    """Test basic memory manager operations."""
    
    def test_add_message(self, memory_manager):
        """Test adding a single message."""
        memory_manager.add_message("session1", "user", "Hello")
        
        history = memory_manager.get_history("session1")
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
    
    def test_add_multiple_messages(self, memory_manager):
        """Test adding multiple messages."""
        memory_manager.add_message("session1", "user", "Hello")
        memory_manager.add_message("session1", "assistant", "Hi there!")
        memory_manager.add_message("session1", "user", "How are you?")
        
        history = memory_manager.get_history("session1")
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
        assert history[2]["role"] == "user"
    
    def test_multiple_sessions(self, memory_manager):
        """Test that different sessions are kept separate."""
        memory_manager.add_message("session1", "user", "Message 1")
        memory_manager.add_message("session2", "user", "Message 2")
        
        history1 = memory_manager.get_history("session1")
        history2 = memory_manager.get_history("session2")
        
        assert len(history1) == 1
        assert len(history2) == 1
        assert history1[0]["content"] == "Message 1"
        assert history2[0]["content"] == "Message 2"
    
    def test_clear_session(self, memory_manager):
        """Test clearing a session."""
        memory_manager.add_message("session1", "user", "Hello")
        memory_manager.add_message("session1", "assistant", "Hi!")
        
        assert memory_manager.get_session_count() == 1
        
        memory_manager.clear_session("session1")
        
        assert memory_manager.get_session_count() == 0
        # Getting history for cleared session should create empty session
        history = memory_manager.get_history("session1")
        assert len(history) == 0
    
    def test_message_has_timestamp(self, memory_manager):
        """Test that messages are stored with timestamps."""
        memory_manager.add_message("session1", "user", "Hello")
        
        session_info = memory_manager.get_session_info("session1")
        assert session_info is not None
        assert len(session_info["messages"]) == 1
        assert "timestamp" in session_info["messages"][0]
        assert isinstance(session_info["messages"][0]["timestamp"], datetime)


class TestSlidingWindow:
    """Test sliding window functionality."""
    
    def test_sliding_window_keeps_last_10_pairs(self, memory_manager_with_mock_client):
        """Test that sliding window keeps exactly last 10 message pairs."""
        # Add 15 message pairs (30 messages)
        for i in range(15):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        session_info = memory_manager_with_mock_client.get_session_info("session1")
        
        # Should have exactly 20 messages (10 pairs) after sliding window
        assert len(session_info["messages"]) == 20
        
        # Should have the last 10 pairs (messages 5-14)
        assert session_info["messages"][0]["content"] == "User message 5"
        assert session_info["messages"][-1]["content"] == "Assistant response 14"
    
    def test_sliding_window_creates_summary(self, memory_manager_with_mock_client):
        """Test that sliding window creates a summary of old messages."""
        # Add 11 message pairs to trigger summarization
        for i in range(11):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        session_info = memory_manager_with_mock_client.get_session_info("session1")
        
        # Should have a summary
        assert session_info["summary"] is not None
        assert len(session_info["summary"]) > 0
        
        # Summary should be included in history
        history = memory_manager_with_mock_client.get_history("session1")
        assert any("[Previous conversation summary:" in msg["content"] for msg in history)
    
    def test_sliding_window_without_client(self, memory_manager):
        """Test sliding window behavior when no API client is available."""
        # Add 11 message pairs
        for i in range(11):
            memory_manager.add_message("session1", "user", f"User message {i}")
            memory_manager.add_message("session1", "assistant", f"Assistant response {i}")
        
        session_info = memory_manager.get_session_info("session1")
        
        # Should still keep only 20 messages
        assert len(session_info["messages"]) == 20
        
        # Summary should be None since no client
        assert session_info["summary"] is None
    
    def test_sliding_window_with_odd_messages(self, memory_manager_with_mock_client):
        """Test sliding window with incomplete pairs."""
        # Add 10 complete pairs + 1 user message
        for i in range(10):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        memory_manager_with_mock_client.add_message("session1", "user", "Extra user message")
        
        session_info = memory_manager_with_mock_client.get_session_info("session1")
        
        # Should have 21 messages (10 pairs + 1 user message)
        assert len(session_info["messages"]) == 21
        
        # No summary should be created yet (only 10 complete pairs)
        assert session_info["summary"] is None
    
    def test_summary_format_in_history(self, memory_manager_with_mock_client):
        """Test that summary is properly formatted in history."""
        # Add enough messages to trigger summarization
        for i in range(12):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        history = memory_manager_with_mock_client.get_history("session1")
        
        # First message should be the summary
        assert history[0]["role"] == "user"
        assert "[Previous conversation summary:" in history[0]["content"]
        
        # Remaining messages should be the recent 20 messages
        assert len(history) == 21  # 1 summary + 20 recent messages


class TestAutoExpiry:
    """Test auto-expiry functionality."""
    
    def test_expire_idle_sessions(self, memory_manager):
        """Test that idle sessions are expired after 30 minutes."""
        # Add messages to multiple sessions
        memory_manager.add_message("session1", "user", "Hello")
        memory_manager.add_message("session2", "user", "Hi")
        memory_manager.add_message("session3", "user", "Hey")
        
        assert memory_manager.get_session_count() == 3
        
        # Manually set last_activity to simulate old sessions
        current_time = time.time()
        _sessions["session1"]["last_activity"] = current_time - (IDLE_EXPIRE_SECONDS + 100)
        _sessions["session2"]["last_activity"] = current_time - (IDLE_EXPIRE_SECONDS + 50)
        _sessions["session3"]["last_activity"] = current_time - 100  # Recent
        
        # Expire idle sessions
        expired_count = memory_manager.expire_idle_sessions()
        
        assert expired_count == 2
        assert memory_manager.get_session_count() == 1
        assert memory_manager.get_session_info("session3") is not None
        assert memory_manager.get_session_info("session1") is None
        assert memory_manager.get_session_info("session2") is None
    
    def test_no_expiry_for_active_sessions(self, memory_manager):
        """Test that active sessions are not expired."""
        memory_manager.add_message("session1", "user", "Hello")
        memory_manager.add_message("session2", "user", "Hi")
        
        assert memory_manager.get_session_count() == 2
        
        # Expire idle sessions (none should be expired)
        expired_count = memory_manager.expire_idle_sessions()
        
        assert expired_count == 0
        assert memory_manager.get_session_count() == 2
    
    def test_activity_updates_timestamp(self, memory_manager):
        """Test that adding messages updates the last_activity timestamp."""
        memory_manager.add_message("session1", "user", "Hello")
        
        session_info = memory_manager.get_session_info("session1")
        initial_activity = session_info["last_activity"]
        
        # Wait a bit and add another message
        time.sleep(0.1)
        memory_manager.add_message("session1", "assistant", "Hi!")
        
        session_info = memory_manager.get_session_info("session1")
        updated_activity = session_info["last_activity"]
        
        assert updated_activity > initial_activity
    
    def test_get_history_updates_timestamp(self, memory_manager):
        """Test that getting history updates the last_activity timestamp."""
        memory_manager.add_message("session1", "user", "Hello")
        
        session_info = memory_manager.get_session_info("session1")
        initial_activity = session_info["last_activity"]
        
        # Wait a bit and get history
        time.sleep(0.1)
        memory_manager.get_history("session1")
        
        session_info = memory_manager.get_session_info("session1")
        updated_activity = session_info["last_activity"]
        
        assert updated_activity > initial_activity


class TestSummaryGeneration:
    """Test conversation summarization."""
    
    def test_summarize_conversation_with_mock(self, memory_manager_with_mock_client):
        """Test that summarization calls Claude API correctly."""
        # Add 11 pairs to trigger summarization
        for i in range(11):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        # Check that the mock was called
        assert memory_manager_with_mock_client.client.messages.create.called
        
        # Check the call arguments
        call_args = memory_manager_with_mock_client.client.messages.create.call_args
        assert call_args[1]["model"] == "claude-3-5-sonnet-20241022"
        assert call_args[1]["max_tokens"] == 200
        assert "Summarize this conversation" in call_args[1]["messages"][0]["content"]
    
    def test_summarize_preserves_key_details(self, memory_manager_with_mock_client):
        """Test that summarization prompt asks for key student details."""
        # Add messages with student details
        memory_manager_with_mock_client.add_message("session1", "user", "I want to study in USA")
        memory_manager_with_mock_client.add_message("session1", "assistant", "Great choice!")
        
        # Add more pairs to trigger summarization
        for i in range(10):
            memory_manager_with_mock_client.add_message("session1", "user", f"Question {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Answer {i}")
        
        # Check that the prompt mentions key details
        call_args = memory_manager_with_mock_client.client.messages.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        
        assert "scores" in prompt.lower()
        assert "country" in prompt.lower()
        assert "course" in prompt.lower()
        assert "budget" in prompt.lower()
    
    def test_summarize_handles_api_error(self, memory_manager_with_mock_client):
        """Test that summarization handles API errors gracefully."""
        # Make the mock raise an exception
        memory_manager_with_mock_client.client.messages.create.side_effect = Exception("API Error")
        
        # Add 11 pairs to trigger summarization
        for i in range(11):
            memory_manager_with_mock_client.add_message("session1", "user", f"User message {i}")
            memory_manager_with_mock_client.add_message("session1", "assistant", f"Assistant response {i}")
        
        session_info = memory_manager_with_mock_client.get_session_info("session1")
        
        # Should have a fallback summary
        assert session_info["summary"] is not None
        assert "summarization failed" in session_info["summary"].lower()
    
    def test_no_summarization_without_client(self, memory_manager):
        """Test that no summarization occurs without API client."""
        # Add 11 pairs
        for i in range(11):
            memory_manager.add_message("session1", "user", f"User message {i}")
            memory_manager.add_message("session1", "assistant", f"Assistant response {i}")
        
        session_info = memory_manager.get_session_info("session1")
        
        # Should not have a summary
        assert session_info["summary"] is None


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_convenience_add_message(self):
        """Test the convenience add_message function."""
        from app.utils.memory import add_message, get_history
        
        _sessions.clear()
        add_message("session1", "user", "Hello")
        
        history = get_history("session1")
        assert len(history) == 1
        assert history[0]["content"] == "Hello"
    
    def test_convenience_clear_session(self):
        """Test the convenience clear_session function."""
        from app.utils.memory import add_message, clear_session, get_memory_manager
        
        _sessions.clear()
        add_message("session1", "user", "Hello")
        
        assert get_memory_manager().get_session_count() == 1
        
        clear_session("session1")
        
        assert get_memory_manager().get_session_count() == 0
    
    def test_convenience_expire_idle_sessions(self):
        """Test the convenience expire_idle_sessions function."""
        from app.utils.memory import add_message, expire_idle_sessions
        
        _sessions.clear()
        add_message("session1", "user", "Hello")
        
        # Manually set old timestamp
        _sessions["session1"]["last_activity"] = time.time() - (IDLE_EXPIRE_SECONDS + 100)
        
        expired = expire_idle_sessions()
        
        assert expired == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_session(self, memory_manager):
        """Test getting history for a session with no messages."""
        history = memory_manager.get_history("new_session")
        assert len(history) == 0
    
    def test_exactly_10_pairs(self, memory_manager):
        """Test behavior with exactly 10 message pairs."""
        for i in range(10):
            memory_manager.add_message("session1", "user", f"User {i}")
            memory_manager.add_message("session1", "assistant", f"Assistant {i}")
        
        session_info = memory_manager.get_session_info("session1")
        
        # Should have exactly 20 messages, no summary
        assert len(session_info["messages"]) == 20
        assert session_info["summary"] is None
    
    def test_clear_nonexistent_session(self, memory_manager):
        """Test clearing a session that doesn't exist."""
        # Should not raise an error
        memory_manager.clear_session("nonexistent")
        assert memory_manager.get_session_count() == 0
    
    def test_session_info_for_nonexistent_session(self, memory_manager):
        """Test getting info for a session that doesn't exist."""
        info = memory_manager.get_session_info("nonexistent")
        assert info is None
