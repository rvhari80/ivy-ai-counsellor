# IVY AI Counsellor - System Architecture

## Overview

This document describes the system architecture, data flow, and key design decisions for the IVY AI Counsellor application.

## System Components

### 1. Backend (FastAPI)

**Location:** `backend/app/`

#### Configuration Layer (`config/`)
- **settings.py**: Centralized configuration using Pydantic Settings
- **constants.py**: Application constants
- **logging.py**: Logging configuration

#### Core Layer (`core/`)
- **middleware.py**: CORS, request logging, error handling
- **exceptions.py**: Custom exception classes
- **dependencies.py**: FastAPI dependency injection
- **security.py**: Rate limiting

#### Data Layer (`models/`)
- **database.py**: SQLite schema and database helpers
- **schemas.py**: Pydantic models for API requests/responses

#### Business Logic (`services/`)
- **rag_service.py**: RAG query pipeline
- **intent_service.py**: Intent classification and lead scoring
- **notification_service.py**: Email and WhatsApp notifications
- **pdf_service.py**: PDF ingestion and chunking
- **gap_report_service.py**: Weekly gap analysis
- **fallback_service.py**: Fallback response handling

#### API Layer (`routes/`)
- **api.py**: Router aggregator
- **chat.py**: Chat endpoint
- **admin.py**: Admin endpoints (PDF upload, etc.)
- **dashboard.py**: Dashboard endpoints (stats, analytics)
- **whatsapp.py**: WhatsApp webhook
- **health.py**: Health check

#### Utilities (`utils/`)
- **chunker.py**: Text chunking for RAG
- **embedder.py**: OpenAI embedding wrapper
- **memory.py**: Conversation memory management

### 2. Frontend (React)

**Location:** `frontend/src/`

- **components/**: React components
  - `chat/`: Chat widget and message components
  - `dashboard/`: Admin and counsellor dashboards
  - `common/`: Reusable components
- **services/**: API client for backend communication
- **hooks/**: Custom React hooks
- **utils/**: Frontend utilities

### 3. Data Storage

#### SQLite Database
- **conversations**: Chat history with metadata
- **leads**: Qualified leads with extracted profiles
- **unanswered_queries**: Questions the AI couldn't answer (for gap analysis)
- **pdf_library**: Metadata for uploaded PDFs

#### Pinecone Vector Database
- Stores document embeddings for semantic search
- Namespace: `ivy`
- Metadata: source_pdf, category, chunk_index, page_number

#### File Storage
- **data/uploads/**: Uploaded PDF files
- **data/exports/**: Generated reports
- **logs/**: Application logs

---

## Data Flow

### 1. Chat Flow

```
User Input
    ↓
[FastAPI] /api/v1/chat
    ↓
[Memory] Load conversation history
    ↓
[RAG Service]
    ├─→ [Embedder] Generate query embedding
    ├─→ [Pinecone] Semantic search (top-k docs)
    └─→ [Claude] Generate response with context
    ↓
[Database] Save conversation
    ↓
[Intent Check] Every 3rd message
    ├─→ [Intent Service] Classify intent & extract profile
    ├─→ [Database] Upsert lead if qualified
    └─→ [Notification Service] Send alerts if hot lead
    ↓
Response to User
```

### 2. PDF Ingestion Flow

```
Admin Uploads PDF
    ↓
[Admin API] /api/v1/admin/upload-pdf
    ↓
[PDF Service]
    ├─→ [PyMuPDF] Extract text
    ├─→ [Chunker] Split into chunks
    ├─→ [Embedder] Generate embeddings
    ├─→ [Pinecone] Upsert vectors
    └─→ [Database] Save metadata
    ↓
Success Response
```

### 3. Intent Classification Flow

```
Triggered (every 3rd message)
    ↓
[Intent Service]
    ├─→ [Memory] Get full conversation history
    ├─→ [Claude] Analyze conversation
    └─→ Extract: intent_level, lead_score, profile
    ↓
[Database] Upsert lead
    ↓
If lead_score ≥ threshold:
    ├─→ [Notification Service]
    │   ├─→ Check cooldown
    │   ├─→ Send WhatsApp alert
    │   └─→ Send email alert
    └─→ [Database] Mark as notified
```

### 4. Gap Report Flow

```
Weekly Schedule (Monday 9 AM IST)
    ↓
[Gap Report Service]
    ├─→ [Database] Query top unanswered queries (last 7 days)
    ├─→ Format report
    └─→ [SendGrid] Email to admin
```

---

## Key Design Decisions

### 1. Centralized Configuration

**Decision:** Use Pydantic Settings for all environment variables

**Rationale:**
- Type-safe configuration with validation
- Single source of truth
- Easy to test with different configs
- Auto-documentation of settings

**Implementation:** `backend/app/config/settings.py`

### 2. Modular Service Layer

**Decision:** Separate business logic into focused service modules

**Rationale:**
- Single Responsibility Principle
- Easier testing and mocking
- Clear separation of concerns
- Future-proof for microservices migration

**Services:**
- RAG, Intent, Notification, PDF, Gap Report, Fallback

### 3. Async-First Architecture

**Decision:** Use async/await throughout the stack

**Rationale:**
- Better performance for I/O-bound operations
- Required for LLM API calls (Anthropic, OpenAI)
- Non-blocking database operations
- Scalable for concurrent users

**Implementation:** FastAPI with aiosqlite, AsyncAnthropic, AsyncOpenAI

### 4. RAG Pipeline

**Decision:** Pinecone + OpenAI embeddings + Claude

**Rationale:**
- **Pinecone:** Fast, managed vector database
- **OpenAI embeddings:** High-quality, cost-effective
- **Claude:** Best-in-class reasoning and instruction following

**Alternative considered:** Local embeddings (Sentence Transformers) - rejected due to quality/performance tradeoffs

### 5. Intent Classification Triggers

**Decision:** Run intent classification every 3rd message

**Rationale:**
- Balance between responsiveness and cost
- Enough context for accurate classification
- Prevents rate limit issues
- Reduces API costs

**Alternative considered:** Every message - too expensive; Manual trigger - too slow

### 6. Notification Strategy

**Decision:** Parallel WhatsApp + Email with cooldown

**Rationale:**
- Redundancy (if one channel fails)
- Immediate visibility for counsellors
- Cooldown prevents spam
- Async for non-blocking

**Implementation:** `asyncio.gather()` for parallel sends

### 7. Database Choice

**Decision:** SQLite for MVP

**Rationale:**
- Zero setup, file-based
- Sufficient for single-server deployment
- Easy backups
- Supports async with aiosqlite

**Migration path:** Can migrate to PostgreSQL for multi-server deployment

### 8. Fallback Handling

**Decision:** Multi-tiered fallback strategy

**Rationale:**
- Graceful degradation
- Always provide some response
- Track gaps for improvement

**Tiers:**
1. RAG retrieval (if similarity > threshold)
2. Canned response for common patterns
3. Human handoff prompt

---

## Security Considerations

1. **API Keys:** Stored in environment variables, never in code
2. **Rate Limiting:** SlowAPI for per-IP rate limiting
3. **CORS:** Configurable allowed origins
4. **Input Validation:** Pydantic models for all inputs
5. **SQL Injection:** Parameterized queries only
6. **Logging:** Sensitive data (API keys, personal info) never logged

---

## Scalability Considerations

### Current Limitations (SQLite)
- Single-server deployment
- ~100 concurrent users
- File-based database

### Future Improvements
1. **Database:** Migrate to PostgreSQL for multi-server
2. **Caching:** Add Redis for session state
3. **Load Balancing:** Nginx + multiple FastAPI instances
4. **Queuing:** Celery for background jobs
5. **Monitoring:** Prometheus + Grafana
6. **CDN:** Static assets via CloudFront/Cloudflare

---

## Testing Strategy

### Unit Tests
- Individual functions in isolation
- Mock external services (Anthropic, OpenAI, Pinecone)
- Fast, no I/O

### Integration Tests
- Multiple services working together
- In-memory database
- Mock only external APIs

### End-to-End Tests
- Full user workflows
- Real database (test instance)
- Mock external APIs

**Location:** `backend/tests/`

---

## Monitoring and Observability

### Logs
- **Location:** `logs/`
- **Rotation:** 10 MB max, 5 backups
- **Levels:** DEBUG (dev), INFO (prod), ERROR (separate file)

### Metrics (Planned)
- Request latency
- RAG retrieval quality
- Intent classification accuracy
- Notification success rate
- API error rates

### Alerts (Planned)
- Database connection failures
- External API failures (Anthropic, Pinecone)
- High error rates
- Hot lead notifications

---

## Deployment Architecture

### Development
```
Local Machine
├── Backend (uvicorn --reload)
├── Frontend (npm start)
└── Data (local SQLite + uploads)
```

### Production (Docker)
```
Docker Compose
├── Backend Container
│   ├── FastAPI + Uvicorn
│   ├── Volume: /data
│   └── Volume: /logs
├── Frontend Container
│   ├── Nginx + React SPA
│   └── Reverse proxy to backend
└── Network: ivy-network
```

### Production (Cloud - Future)
```
AWS/GCP/Azure
├── Load Balancer
├── App Servers (2+)
│   └── Docker containers
├── PostgreSQL (RDS)
├── Redis (ElastiCache)
├── S3 (file storage)
└── CloudWatch (monitoring)
```

---

## Dependencies

### Critical
- **FastAPI:** Web framework
- **Anthropic:** LLM inference
- **OpenAI:** Embeddings
- **Pinecone:** Vector database

### Important
- **SendGrid:** Email notifications
- **PyMuPDF:** PDF processing
- **APScheduler:** Background jobs

### Optional
- **WhatsApp API:** Alternative notification channel

---

## Performance Benchmarks (Target)

- **Chat Response Time:** < 3 seconds (p95)
- **PDF Ingestion:** < 10 seconds per MB
- **Intent Classification:** < 2 seconds
- **Database Query:** < 50ms (p99)
- **API Throughput:** 100+ req/sec

---

## Future Enhancements

1. **Multi-language Support:** Hindi, Tamil, Telugu
2. **Voice Interface:** Speech-to-text + text-to-speech
3. **Advanced Analytics:** Conversion funnel, A/B testing
4. **CRM Integration:** Salesforce, HubSpot
5. **Mobile Apps:** iOS/Android native apps
6. **Advanced RAG:** Graph RAG, multi-hop reasoning

---

**Document Version:** 1.0
**Last Updated:** 2026-02-22
**Author:** IVY Development Team
