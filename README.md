# IVY AI Counsellor

> RAG-based AI chat agent for IVY Overseas study abroad counseling

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)

## Overview

IVY AI Counsellor is an intelligent conversational agent designed to assist students with study abroad inquiries. It leverages:

- **RAG (Retrieval-Augmented Generation)** using Pinecone vector database
- **Claude Sonnet 4.5** for natural language understanding and generation
- **OpenAI embeddings** for semantic search
- **Intent classification** for lead scoring and qualification
- **Automated notifications** via email and WhatsApp for hot leads
- **Gap analysis reporting** to identify knowledge base improvements

## Features

✅ **Intelligent Conversations** - Context-aware responses using RAG
✅ **Lead Qualification** - Automatic scoring based on conversation analysis
✅ **Multi-channel Notifications** - Email & WhatsApp alerts for high-value leads
✅ **PDF Knowledge Base** - Ingest and search through counseling materials
✅ **Admin Dashboard** - Monitor conversations, leads, and system performance
✅ **Fallback Handling** - Graceful degradation when answers aren't found
✅ **Gap Reporting** - Weekly analysis of unanswered queries

---

## Project Structure

```
ivy-ai-counsellor/
├── backend/                    # Python FastAPI application
│   ├── app/
│   │   ├── config/            # Configuration management
│   │   ├── core/              # Core app components (middleware, exceptions)
│   │   ├── models/            # Database models and schemas
│   │   ├── services/          # Business logic (RAG, intent, notifications)
│   │   ├── routes/            # API endpoints
│   │   ├── utils/             # Utilities (chunking, embeddings)
│   │   └── main.py            # Application entry point
│   ├── tests/                 # Test suite
│   └── requirements/          # Dependencies (base, dev, prod)
│
├── frontend/                   # React application
│   └── src/
│       ├── components/        # React components
│       └── services/          # API client
│
├── data/                      # Application data
│   ├── databases/            # SQLite files
│   ├── uploads/              # Uploaded PDFs
│   └── exports/              # Generated reports
│
├── logs/                      # Application logs
├── docs/                      # Documentation
├── docker/                    # Docker configurations
└── scripts/                   # Utility scripts
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **API Keys:**
  - Anthropic (Claude)
  - OpenAI (embeddings)
  - Pinecone (vector database)
  - SendGrid (email notifications, optional)
  - WhatsApp Business API (optional)

### Installation

1. **Clone the repository:**

```bash
git clone <repository-url>
cd ivy-ai-counsellor
```

2. **Set up environment variables:**

```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Install dependencies:**

```bash
# Using Make (recommended)
make install-dev

# Or manually
cd backend && pip install -r requirements/dev.txt
cd ../frontend && npm install
```

### Running Locally

**Option 1: Using Make**

```bash
# Start backend
make backend

# Start frontend (in another terminal)
make frontend
```

**Option 2: Using Docker Compose**

```bash
make dev
# or
docker-compose up
```

**Option 3: Manual**

```bash
# Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm start
```

Visit:
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Frontend:** http://localhost:3000

---

## Configuration

All configuration is managed through environment variables (see `.env.example`).

### Key Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `OPENAI_API_KEY` | OpenAI API key for embeddings | Required |
| `PINECONE_API_KEY` | Pinecone vector DB key | Required |
| `DATABASE_URL` | SQLite database path | `./data/databases/ivy.db` |
| `HOT_LEAD_SCORE_THRESHOLD` | Score threshold for hot leads | `80` |
| `RAG_TOP_K` | Number of docs to retrieve | `5` |
| `ENVIRONMENT` | Environment (development/staging/production) | `development` |

See [`backend/app/config/settings.py`](backend/app/config/settings.py) for all options.

---

## API Documentation

### Core Endpoints

#### Chat
- `POST /api/v1/chat` - Send a message to the AI counsellor

#### Admin
- `POST /api/v1/admin/upload-pdf` - Upload PDF to knowledge base
- `GET /api/v1/admin/conversations` - List all conversations
- `GET /api/v1/admin/leads` - List qualified leads

#### Dashboard
- `GET /api/v1/dashboard/stats` - Get system statistics
- `GET /api/v1/dashboard/unanswered` - Get unanswered queries

#### Health
- `GET /api/v1/health` - Health check endpoint

Full API documentation available at `/docs` when running the backend.

---

## Development

### Running Tests

```bash
# Run all tests
make test

# Run with coverage report
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

### Code Quality

```bash
# Format code
make format

# Run linters
make lint
```

### Database

The application uses SQLite with the following tables:
- `conversations` - Chat history
- `leads` - Qualified leads with profile data
- `unanswered_queries` - Questions the AI couldn't answer
- `pdf_library` - Uploaded PDF metadata

---

## Deployment

### Docker Deployment

```bash
# Build images
make build

# Start services
make up

# View logs
make logs

# Stop services
make down
```

### Production Checklist

- [ ] Update `.env` with production API keys
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Configure CORS `ALLOWED_ORIGINS`
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup for `data/databases/`
- [ ] Set up monitoring and alerting
- [ ] Review rate limiting settings

---

## Architecture

### RAG Pipeline

1. **User Query** → Embedding (OpenAI)
2. **Vector Search** → Pinecone (top-k similar documents)
3. **Context Assembly** → Combine query + retrieved docs
4. **LLM Generation** → Claude generates response
5. **Response** → Delivered to user

### Intent Classification

Runs after every 3rd message:
- Analyzes conversation history
- Extracts user profile (name, course, country, budget, etc.)
- Assigns lead score (0-100)
- Classifies intent (BROWSING → RESEARCHING → CONSIDERING → HOT_LEAD)
- Triggers notifications for hot leads (score ≥ 80)

### Notification Flow

1. **Lead qualification** (score ≥ threshold)
2. **Check cooldown** (prevent spam)
3. **Send notifications** (email + WhatsApp in parallel)
4. **Update database** (mark as notified)

---

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests: `make test`
4. Format code: `make format`
5. Submit a pull request

---

## Troubleshooting

### Common Issues

**Backend won't start:**
- Check `.env` file exists and has all required API keys
- Ensure Python 3.11+ is installed: `python --version`
- Try: `cd backend && pip install -r requirements.txt`

**Database errors:**
- Delete `data/databases/ivy.db` and restart (recreates schema)

**Pinecone connection issues:**
- Verify `PINECONE_API_KEY` and `PINECONE_INDEX` in `.env`
- Check index exists in Pinecone console

**Tests failing:**
- Install dev dependencies: `make install-dev`
- Check logs in `logs/` directory

---

## License

[Your License Here]

---

## Support

For issues, questions, or contributions:
- **Email:** admin@ivyoverseas.com
- **Issues:** [GitHub Issues](<repository-url>/issues)

---

**Built with ❤️ for IVY Overseas**
