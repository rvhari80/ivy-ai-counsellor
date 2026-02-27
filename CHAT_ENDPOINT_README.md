# Chat Endpoint Documentation

## Overview

The `/api/chat` endpoint provides a streaming chat interface with RAG (Retrieval-Augmented Generation) capabilities for the IVY AI Counsellor platform.

## Endpoint Details

**URL:** `POST /api/chat`

**Content-Type:** `application/json`

**Response Type:** `text/event-stream` (Server-Sent Events)

## Request Format

```json
{
  "session_id": "string (1-100 chars, required)",
  "message": "string (1-500 chars, required)",
  "metadata": {
    "optional": "dict"
  }
}
```

### Request Parameters

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `session_id` | string | Yes | 1-100 characters | Unique identifier for the conversation session |
| `message` | string | Yes | 1-500 characters, non-empty after trim | User's message/question |
| `metadata` | dict | No | - | Optional metadata for tracking/analytics |

## Response Format

The endpoint returns a streaming response using Server-Sent Events (SSE) format.

### Streaming Chunks

Each chunk follows this format:

```
data: {"token": "...", "done": false}
```

### Final Chunk

```
data: {"token": "", "done": true, "session_id": "..."}
```

### Example Response Stream

```
data: {"token": "Hello", "done": false}

data: {"token": " there", "done": false}

data: {"token": "!", "done": false}

data: {"token": "", "done": true, "session_id": "test_session_001"}
```

## Features

### 1. Input Validation
- ✅ Maximum 500 characters per message
- ✅ No empty messages (whitespace-only messages rejected)
- ✅ Session ID validation (1-100 characters)

### 2. Rate Limiting
- ✅ Maximum 30 messages per session per hour
- ✅ Returns HTTP 429 when limit exceeded
- ✅ Automatic cleanup of old timestamps

### 3. RAG Integration
- ✅ Queries Pinecone vector database for relevant context
- ✅ Uses Claude API for response generation
- ✅ Maintains conversation history per session
- ✅ Streams responses token-by-token

### 4. Database Logging
- ✅ Every conversation logged to SQLite
- ✅ Includes: session_id, user_message, ai_response, timestamp, platform
- ✅ Non-blocking (doesn't fail request if logging fails)

### 5. Error Handling
- ✅ Never exposes internal errors to users
- ✅ Generic error messages for all failures
- ✅ Comprehensive logging for debugging
- ✅ Graceful degradation

## Status Codes

| Code | Description |
|------|-------------|
| 200 | Success - streaming response |
| 422 | Validation error (empty message, too long, etc.) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Error Responses

### Rate Limit Exceeded (429)

```json
{
  "detail": "Please wait before sending another message"
}
```

### Validation Error (422)

```json
{
  "detail": [
    {
      "loc": ["body", "message"],
      "msg": "ensure this value has at most 500 characters",
      "type": "value_error.any_str.max_length"
    }
  ]
}
```

### Internal Error (500)

```json
{
  "detail": "An unexpected error occurred. Please try again later."
}
```

## Usage Examples

### Python (httpx)

```python
import httpx
import json

async def chat_stream():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/chat",
            json={
                "session_id": "user_123",
                "message": "What are the requirements for studying in Canada?"
            },
            headers={"Accept": "text/event-stream"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["done"]:
                        print(f"\nSession: {data['session_id']}")
                    else:
                        print(data["token"], end="", flush=True)
```

### JavaScript (Fetch API)

```javascript
async function chatStream(sessionId, message) {
  const response = await fetch('http://localhost:8000/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify({
      session_id: sessionId,
      message: message
    })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        if (data.done) {
          console.log(`\nSession: ${data.session_id}`);
        } else {
          process.stdout.write(data.token);
        }
      }
    }
  }
}
```

### cURL

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "test_session",
    "message": "Tell me about studying abroad"
  }' \
  --no-buffer
```

## Testing

Run the provided test script:

```bash
python test_chat_endpoint.py
```

This will test:
1. ✅ Valid chat request with streaming
2. ✅ Empty message validation
3. ✅ Message length validation
4. ✅ Rate limiting (30 messages/hour)
5. ✅ Database logging

## Database Schema

Conversations are logged to the `conversations` table:

```sql
CREATE TABLE conversations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    user_message  TEXT NOT NULL,
    ai_response   TEXT NOT NULL,
    intent_level  TEXT,
    lead_score    INTEGER DEFAULT 0,
    rag_score     REAL,
    fallback_type TEXT,
    platform      TEXT DEFAULT 'web',
    timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Query recent conversations:

```bash
sqlite3 ivy_counsellor.db "SELECT session_id, user_message, timestamp FROM conversations ORDER BY timestamp DESC LIMIT 10;"
```

## Rate Limiting Details

- **Limit:** 30 messages per session per hour
- **Scope:** Per session_id (not per IP)
- **Storage:** In-memory (resets on server restart)
- **Cleanup:** Automatic removal of timestamps older than 1 hour

## Security Considerations

1. **Error Masking:** Internal errors never exposed to users
2. **Input Validation:** Strict validation on all inputs
3. **Rate Limiting:** Prevents abuse and excessive API costs
4. **CORS:** Configure `allow_origins` appropriately for production
5. **Logging:** All errors logged with full stack traces for debugging

## Performance

- **Streaming:** Responses stream token-by-token for better UX
- **Non-blocking:** Database logging doesn't block response
- **Connection Headers:** Includes cache control and keep-alive headers
- **Nginx Compatibility:** Includes `X-Accel-Buffering: no` header

## Monitoring

Key metrics to monitor:

1. **Rate limit hits:** Check logs for "Rate limit exceeded" warnings
2. **Database failures:** Check logs for "Failed to log conversation" errors
3. **RAG errors:** Check logs for "Error in RAG query service" errors
4. **Response times:** Monitor streaming latency
5. **Token usage:** Track Claude API token consumption per session

## Troubleshooting

### Issue: Rate limit hit too quickly

**Solution:** Increase `MAX_MESSAGES_PER_HOUR` in `app/routes/chat.py`

### Issue: Streaming not working

**Solution:** Ensure client accepts `text/event-stream` and doesn't buffer

### Issue: Database logging fails

**Solution:** Check database permissions and disk space. Logging failures don't affect response.

### Issue: Empty responses

**Solution:** Check Pinecone and Anthropic API keys in `.env` file

## Environment Variables

Required environment variables:

```bash
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX=ivy-counsellor
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-5
OPENAI_API_KEY=your_openai_key  # For embeddings
DATABASE_URL=sqlite+aiosqlite:///./ivy_counsellor.db
```

## Future Enhancements

- [ ] Redis-based rate limiting for multi-instance deployments
- [ ] WebSocket support as alternative to SSE
- [ ] Message queue for async database logging
- [ ] Prometheus metrics endpoint
- [ ] Session timeout and cleanup
- [ ] Message history retrieval endpoint
- [ ] Admin override for rate limits
