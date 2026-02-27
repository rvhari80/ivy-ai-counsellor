# Conversation Memory Manager

## Overview

The conversation memory manager (`app/utils/memory.py`) provides intelligent conversation history management with sliding window, automatic summarization, and session expiry features.

## Features

### 1. **Session-based Storage**
- Stores conversations per `session_id` in an in-memory Python dictionary
- Each session contains:
  - List of messages with `role` (user/assistant), `content`, and `timestamp`
  - Last activity timestamp for auto-expiry
  - Optional conversation summary

### 2. **Sliding Window (10 Message Pairs)**
- Automatically keeps only the last 10 message pairs (20 messages total)
- When conversation exceeds 10 pairs, older messages are summarized
- Recent context is always preserved

### 3. **Automatic Summarization**
- Uses Claude API to summarize older messages when sliding window is triggered
- Summarization prompt: "Summarise this conversation in 3 sentences preserving key student details like scores, country interest, course and budget"
- Summary is included as a system-like message in conversation history
- Gracefully handles API errors with fallback messages

### 4. **Auto-Expiry**
- Sessions inactive for 30 minutes are automatically expired
- Call `expire_idle_sessions()` periodically (e.g., via scheduler)
- Activity is updated on every `add_message()` or `get_history()` call

### 5. **Claude API Integration**
- Formatted message history ready for Claude API
- Summary included as user message with special formatting
- Timestamps removed from API output for compatibility

## Usage

### Basic Usage

```python
from app.utils.memory import ConversationMemoryManager

# Initialize manager (reads ANTHROPIC_API_KEY from environment)
manager = ConversationMemoryManager()

# Add messages
manager.add_message("session123", "user", "I want to study in USA")
manager.add_message("session123", "assistant", "Great! What's your budget?")

# Get history for Claude API
history = manager.get_history("session123")
# Returns: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

# Clear session
manager.clear_session("session123")

# Expire idle sessions (call periodically)
expired_count = manager.expire_idle_sessions()
```

### Convenience Functions

```python
from app.utils.memory import add_message, get_history, clear_session, expire_idle_sessions

# These use a global manager instance
add_message("session123", "user", "Hello")
history = get_history("session123")
clear_session("session123")
expired = expire_idle_sessions()
```

## API Reference

### `ConversationMemoryManager`

#### `__init__(anthropic_api_key: Optional[str] = None)`
Initialize the memory manager. If no API key provided, reads from `ANTHROPIC_API_KEY` environment variable.

#### `add_message(session_id: str, role: str, content: str) -> None`
Add a new message to the conversation. Automatically applies sliding window if needed.

#### `get_history(session_id: str) -> list[dict[str, str]]`
Get formatted message history for Claude API. Includes summary if available.

#### `clear_session(session_id: str) -> None`
Remove all data for a session.

#### `expire_idle_sessions() -> int`
Remove sessions inactive for 30+ minutes. Returns count of expired sessions.

#### `get_session_count() -> int`
Get the number of active sessions.

#### `get_session_info(session_id: str) -> Optional[dict]`
Get raw session data for debugging/testing.

## Configuration

```python
# In app/utils/memory.py
MAX_PAIRS = 10  # Keep last 10 message pairs (20 messages)
IDLE_EXPIRE_SECONDS = 30 * 60  # 30 minutes
```

## Testing

### Run Unit Tests

```bash
# Full test suite
pytest tests/test_memory.py -v

# Quick verification
python test_memory_simple.py
```

### Test Coverage

The test suite includes:
- ✅ Basic message operations (add, get, clear)
- ✅ Multiple session isolation
- ✅ Sliding window with 10 pairs limit
- ✅ Summary generation with mocked Claude API
- ✅ Auto-expiry after 30 minutes
- ✅ Timestamp updates on activity
- ✅ Edge cases (empty sessions, exactly 10 pairs, etc.)
- ✅ Error handling (API failures, missing client)
- ✅ Convenience functions

## Integration Example

```python
from fastapi import FastAPI
from app.utils.memory import get_memory_manager
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()
manager = get_memory_manager()

# Schedule periodic cleanup
scheduler = BackgroundScheduler()
scheduler.add_job(manager.expire_idle_sessions, 'interval', minutes=10)
scheduler.start()

@app.post("/chat")
async def chat(session_id: str, message: str):
    # Add user message
    manager.add_message(session_id, "user", message)
    
    # Get conversation history
    history = manager.get_history(session_id)
    
    # Call Claude API with history
    response = await call_claude_api(history)
    
    # Add assistant response
    manager.add_message(session_id, "assistant", response)
    
    return {"response": response}
```

## Architecture Notes

- **In-Memory Storage**: Sessions are stored in a Python dict. For production with multiple workers, consider Redis or similar.
- **Thread Safety**: Current implementation is not thread-safe. Use locks if needed for concurrent access.
- **Persistence**: Sessions are lost on restart. Implement persistence layer if needed.
- **Scalability**: For high-traffic applications, consider distributed session storage.

## Future Enhancements

- [ ] Redis backend for distributed storage
- [ ] Configurable sliding window size
- [ ] Custom summarization prompts per session
- [ ] Session persistence to disk/database
- [ ] Thread-safe operations with locks
- [ ] Metrics and monitoring (session count, expiry rate, etc.)
