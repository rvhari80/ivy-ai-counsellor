"""Simple test to verify memory manager works."""
import sys
sys.path.insert(0, 'c:/Users/WINDOWS11/ivy-ai-counsellor')

from app.utils.memory import ConversationMemoryManager, _sessions

def test_basic():
    """Test basic functionality."""
    _sessions.clear()
    manager = ConversationMemoryManager(anthropic_api_key=None)
    
    # Test 1: Add message
    manager.add_message("test1", "user", "Hello")
    history = manager.get_history("test1")
    assert len(history) == 1
    assert history[0]["content"] == "Hello"
    print("✓ Test 1 passed: Add message")
    
    # Test 2: Multiple messages
    manager.add_message("test1", "assistant", "Hi!")
    manager.add_message("test1", "user", "How are you?")
    history = manager.get_history("test1")
    assert len(history) == 3
    print("✓ Test 2 passed: Multiple messages")
    
    # Test 3: Clear session
    manager.clear_session("test1")
    assert manager.get_session_count() == 0
    print("✓ Test 3 passed: Clear session")
    
    # Test 4: Sliding window (without API)
    _sessions.clear()
    for i in range(15):
        manager.add_message("test2", "user", f"User {i}")
        manager.add_message("test2", "assistant", f"Assistant {i}")
    
    session_info = manager.get_session_info("test2")
    assert len(session_info["messages"]) == 20  # Only last 10 pairs
    print("✓ Test 4 passed: Sliding window keeps 20 messages")
    
    # Test 5: Auto-expiry
    import time
    from app.utils.memory import IDLE_EXPIRE_SECONDS
    
    _sessions.clear()
    manager.add_message("test3", "user", "Hello")
    manager.add_message("test4", "user", "Hi")
    
    # Simulate old session
    _sessions["test3"]["last_activity"] = time.time() - (IDLE_EXPIRE_SECONDS + 100)
    
    expired = manager.expire_idle_sessions()
    assert expired == 1
    assert manager.get_session_count() == 1
    print("✓ Test 5 passed: Auto-expiry")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    try:
        test_basic()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
