# IVY AI Counsellor - Development Guide

## Getting Started

This guide will help you set up your local development environment for the IVY AI Counsellor project.

---

## Prerequisites

### Required Software

1. **Python 3.11 or higher**
   ```bash
   python --version  # Should be 3.11+
   ```

2. **Node.js 18 or higher** (for frontend)
   ```bash
   node --version  # Should be 18+
   ```

3. **Git**
   ```bash
   git --version
   ```

4. **Make** (optional, but recommended)
   - Linux/Mac: Pre-installed
   - Windows: Install via `choco install make` or use Git Bash

### Required API Keys

Before you begin, obtain the following API keys:

- **Anthropic API Key** - [Get it here](https://console.anthropic.com/)
- **OpenAI API Key** - [Get it here](https://platform.openai.com/)
- **Pinecone API Key** - [Get it here](https://www.pinecone.io/)
- **SendGrid API Key** (optional) - [Get it here](https://sendgrid.com/)
- **WhatsApp Business API** (optional) - [Meta for Developers](https://developers.facebook.com/)

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ivy-ai-counsellor
```

### 2. Set Up Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit with your API keys
nano .env  # or use your preferred editor
```

**Minimum required variables:**
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
PINECONE_API_KEY=your-key-here
PINECONE_INDEX=ivy-counsellor
DATABASE_URL=sqlite+aiosqlite:///./data/databases/ivy.db
```

### 3. Install Backend Dependencies

```bash
cd backend
python -m venv .venv

# Activate virtual environment
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements/dev.txt
```

### 4. Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

### 5. Set Up Pinecone Index

Before running the application, create a Pinecone index:

1. Go to [Pinecone Console](https://app.pinecone.io/)
2. Create a new index named `ivy-counsellor`
3. Dimensions: `1536` (for OpenAI text-embedding-3-small)
4. Metric: `cosine`
5. Region: Choose closest to your location

---

## Running the Application

### Method 1: Using Make (Recommended)

```bash
# Start backend (in one terminal)
make backend

# Start frontend (in another terminal)
make frontend
```

### Method 2: Manual Start

**Terminal 1 - Backend:**
```bash
cd backend
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

### Method 3: Docker Compose

```bash
# Build and start all services
make dev
# or
docker-compose up
```

---

## Accessing the Application

Once running, you can access:

- **Backend API:** http://localhost:8000
- **API Documentation (Swagger):** http://localhost:8000/docs
- **API Documentation (ReDoc):** http://localhost:8000/redoc
- **Frontend:** http://localhost:3000
- **Health Check:** http://localhost:8000/health

---

## Project Structure

```
ivy-ai-counsellor/
├── backend/
│   ├── app/
│   │   ├── config/       # Configuration (settings, constants, logging)
│   │   ├── core/         # Core (middleware, exceptions, security)
│   │   ├── models/       # Database models and schemas
│   │   ├── services/     # Business logic
│   │   ├── routes/       # API endpoints
│   │   ├── utils/        # Utilities
│   │   └── main.py       # App entry point
│   ├── tests/            # Test suite
│   └── requirements/     # Dependencies
├── frontend/             # React application
├── data/                 # Application data (gitignored)
├── logs/                 # Log files (gitignored)
├── docs/                 # Documentation
└── docker/               # Docker configs
```

---

## Development Workflow

### 1. Code Organization

#### Adding a New API Endpoint

1. Create route handler in `backend/app/routes/<module>.py`
2. Add business logic in `backend/app/services/<service>.py`
3. Define request/response models in `backend/app/models/schemas.py`
4. Update `backend/app/routes/api.py` if creating a new router

Example:
```python
# backend/app/routes/chat.py
from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag_service import query_rag

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    response = await query_rag(request.message, request.session_id)
    return ChatResponse(response=response)
```

#### Adding a New Service

1. Create file in `backend/app/services/<service_name>.py`
2. Import and use `settings` from `app.config.settings`
3. Add logging: `logger = logging.getLogger(__name__)`
4. Write unit tests in `backend/tests/unit/test_<service_name>.py`

### 2. Configuration Management

All configuration is centralized in `backend/app/config/settings.py`:

```python
from app.config.settings import settings

# Use settings instead of os.getenv()
api_key = settings.ANTHROPIC_API_KEY  # ✅ Good
api_key = os.getenv("ANTHROPIC_API_KEY")  # ❌ Avoid
```

### 3. Database Operations

```python
from app.models.database import get_db

async def my_function():
    async with get_db() as conn:
        cursor = await conn.execute("SELECT * FROM leads")
        rows = await cursor.fetchall()
    return rows
```

---

## Testing

### Running Tests

```bash
# All tests
make test

# Specific test file
cd backend
pytest tests/unit/test_rag.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Writing Tests

Use fixtures from `conftest.py`:

```python
# backend/tests/unit/test_example.py
import pytest

async def test_database(test_db):
    """test_db fixture provides in-memory database"""
    async with test_db.execute("SELECT 1") as cursor:
        result = await cursor.fetchone()
    assert result[0] == 1

def test_conversation(sample_conversation):
    """sample_conversation fixture provides test data"""
    assert len(sample_conversation) == 3
```

---

## Code Quality

### Formatting

```bash
# Format all code
make format

# or manually
cd backend
black app/ tests/
```

### Linting

```bash
# Run all linters
make lint

# or manually
cd backend
ruff check app/ tests/
mypy app/
```

### Pre-commit Checks

Before committing:
```bash
make format
make lint
make test
```

---

## Common Tasks

### Adding a New PDF to Knowledge Base

```bash
# Via API (while backend is running)
curl -X POST http://localhost:8000/api/v1/admin/upload-pdf \
  -F "file=@path/to/document.pdf" \
  -F "category=visa"
```

Categories: `visa`, `university`, `scholarship`, `testprep`, `finance`, `poststudy`, `sop`

### Viewing Logs

```bash
# Real-time logs
tail -f logs/ivy_counsellor.log

# Error logs only
tail -f logs/errors.log

# Search logs
grep "ERROR" logs/ivy_counsellor.log
```

### Database Management

```bash
# View database
sqlite3 data/databases/ivy.db
.tables
SELECT * FROM conversations LIMIT 5;
.exit

# Reset database (development only!)
rm data/databases/ivy.db
# Restart backend (will recreate schema)
```

### Debugging

#### Enable Debug Mode

In `.env`:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

#### Use Python Debugger

```python
# Add breakpoint in code
import ipdb; ipdb.set_trace()

# Or use built-in
breakpoint()
```

#### View FastAPI Debug Info

Visit http://localhost:8000/docs - test endpoints interactively

---

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `PINECONE_API_KEY` | Pinecone API key | `pcsk_...` |
| `PINECONE_INDEX` | Pinecone index name | `ivy-counsellor` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `./data/databases/ivy.db` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Environment name | `development` |
| `HOT_LEAD_SCORE_THRESHOLD` | Score for hot leads | `80` |
| `RAG_TOP_K` | Docs to retrieve | `5` |
| `SENDGRID_API_KEY` | Email service key | - |
| `WHATSAPP_API_KEY` | WhatsApp API key | - |

---

## Troubleshooting

### Backend Won't Start

**Error: "pydantic_settings not found"**
```bash
cd backend
pip install pydantic-settings
```

**Error: "ANTHROPIC_API_KEY not set"**
- Check `.env` file exists in project root
- Verify the key is correct and not expired
- Ensure no quotes around the value

### Database Errors

**Error: "no such table: conversations"**
```bash
# Database schema not initialized
rm data/databases/ivy.db
# Restart backend (will recreate)
```

### Pinecone Errors

**Error: "Index not found"**
- Create index in Pinecone console
- Verify `PINECONE_INDEX` in `.env` matches

**Error: "Dimension mismatch"**
- Ensure Pinecone index dimensions = 1536 (for OpenAI embeddings)

### Frontend Errors

**Error: "Cannot connect to backend"**
- Verify backend is running on port 8000
- Check `REACT_APP_API_URL` in frontend env

---

## Tips and Best Practices

### 1. Use Type Hints
```python
# Good
async def get_lead(session_id: str) -> dict | None:
    ...

# Avoid
async def get_lead(session_id):
    ...
```

### 2. Always Use Async
```python
# Good
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

# Avoid
def fetch_data():
    response = requests.get(url)  # Blocking!
```

### 3. Handle Errors Gracefully
```python
try:
    result = await external_api_call()
except Exception as e:
    logger.error(f"API call failed: {e}")
    return fallback_response()
```

### 4. Log Important Events
```python
logger.info(f"Lead qualified: session={session_id}, score={score}")
logger.error(f"Failed to send notification: {e}")
```

### 5. Write Tests
```python
@pytest.mark.asyncio
async def test_rag_query(mock_pinecone):
    result = await query_rag("test query", "session-123")
    assert result is not None
```

---

## Getting Help

- **Documentation:** Check `docs/` directory
- **API Docs:** http://localhost:8000/docs
- **Issues:** Open a GitHub issue
- **Email:** admin@ivyoverseas.com

---

## Next Steps

1. ✅ Set up development environment
2. ✅ Run the application locally
3. 📖 Read [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the system
4. 🧪 Run tests and explore the codebase
5. 🎯 Pick a task from the backlog and start coding!

---

**Happy Coding! 🚀**
