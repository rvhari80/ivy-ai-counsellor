"""
Pytest configuration and fixtures for IVY AI Counsellor tests.
"""
import pytest
import aiosqlite
from app.models.database import SCHEMA


@pytest.fixture
async def test_db():
    """
    Create an in-memory SQLite database for testing.
    Each test gets a fresh database.
    """
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(SCHEMA)
        await db.commit()
        yield db


@pytest.fixture
def sample_conversation():
    """Sample conversation history for testing."""
    return [
        {"role": "user", "content": "I want to study MS in USA"},
        {
            "role": "assistant",
            "content": "Great! Tell me more about your background. What is your current education level?",
        },
        {
            "role": "user",
            "content": "I have B.Tech in Computer Science with 85% marks. IELTS 7.5",
        },
    ]


@pytest.fixture
def sample_lead_data():
    """Sample lead data for testing."""
    return {
        "name": "Test User",
        "phone": "+919876543210",
        "email": "test@example.com",
        "target_course": "MS Computer Science",
        "target_country": "USA",
        "target_intake": "Fall 2025",
        "budget_inr": 3000000,
        "ielts_score": "7.5",
        "percentage": "85",
    }


@pytest.fixture
def sample_intent_result():
    """Sample intent result for testing."""
    from app.models.schemas import IntentResult, ExtractedProfile

    return IntentResult(
        intent_level="HOT_LEAD",
        lead_score=85,
        extracted_profile=ExtractedProfile(
            name="Test User",
            phone="+919876543210",
            email="test@example.com",
            target_course="MS Computer Science",
            target_country="USA",
            target_intake="Fall 2025",
            budget_inr=3000000,
            ielts_score="7.5",
            percentage="85",
        ),
        conversation_summary="Student wants MS in CS in USA. Has strong profile.",
        recommended_action="Schedule counseling session immediately.",
    )


@pytest.fixture
def sample_pdf_text():
    """Sample PDF text content for testing."""
    return """
    Study in USA - Complete Guide

    The United States offers world-class education opportunities for international students.
    Top universities include MIT, Stanford, Harvard, and UC Berkeley.

    Requirements:
    - Valid passport
    - I-20 form from university
    - Student visa (F-1)
    - Proof of financial support
    - English proficiency (TOEFL/IELTS)

    Estimated costs:
    - Tuition: $30,000 - $60,000 per year
    - Living expenses: $15,000 - $25,000 per year
    """


@pytest.fixture
def sample_chunks():
    """Sample text chunks for testing."""
    return [
        "The United States offers world-class education opportunities.",
        "Top universities include MIT, Stanford, Harvard, and UC Berkeley.",
        "Requirements include valid passport, I-20 form, and student visa.",
        "Estimated tuition costs range from $30,000 to $60,000 per year.",
    ]


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings response."""
    return [[0.1, 0.2, 0.3] for _ in range(4)]


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    return {
        "intent_level": "RESEARCHING",
        "lead_score": 45,
        "extracted_profile": {
            "name": None,
            "phone": None,
            "email": None,
            "target_course": "MS Computer Science",
            "target_country": "USA",
            "target_intake": None,
            "budget_inr": None,
            "ielts_score": None,
            "percentage": None,
        },
        "conversation_summary": "User is exploring MS programs in USA.",
        "recommended_action": "Provide information about top universities and requirements.",
    }
