"""RAG query service for IVY AI Counsellor."""
import os
import logging
from typing import AsyncGenerator
from anthropic import AsyncAnthropic
from pinecone import Pinecone

from app.utils.embedder import embed_text
from app.utils.memory import get_history, add_message

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "ivy-counsellor")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# System prompt for IVY AI Counsellor
SYSTEM_PROMPT = """You are IVY AI Counsellor, a helpful study abroad advisor for IVY Overseas.
Answer only using the provided context. Be warm, clear and specific.
If context is insufficient, say so honestly and offer to connect with a human counsellor.
Always end answers about visas or admissions with: Would you like to speak with one of our expert counsellors for personalised guidance?"""

# ─────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────
_pinecone_client: Pinecone | None = None
_anthropic_client: AsyncAnthropic | None = None

# Token tracking per session
_session_tokens: dict[str, int] = {}


def get_pinecone_client() -> Pinecone:
    """Initialize and return Pinecone client."""
    global _pinecone_client
    if _pinecone_client is None:
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY not set")
        _pinecone_client = Pinecone(api_key=PINECONE_API_KEY)
    return _pinecone_client


def get_anthropic_client() -> AsyncAnthropic:
    """Initialize and return Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


# ─────────────────────────────────────────────────────────────
# RAG Query Service
# ─────────────────────────────────────────────────────────────
async def query_rag(
    student_question: str,
    session_id: str
) -> AsyncGenerator[str, None]:
    """
    Complete RAG query service that:
    1. Embeds the student question using OpenAI text-embedding-3-small
    2. Searches Pinecone for top 3 most relevant chunks
    3. Builds system prompt with context
    4. Calls Claude API with streaming
    5. Tracks tokens per session
    6. Returns streaming response token by token
    
    Args:
        student_question: The student's query
        session_id: Session identifier for conversation tracking
        
    Yields:
        str: Response tokens streamed from Claude
    """
    try:
        # ─────────────────────────────────────────────────────
        # Step 1: Embed the query using OpenAI
        # ─────────────────────────────────────────────────────
        logger.info(f"Embedding query for session {session_id}")
        query_vector = await embed_text(student_question)
        
        # ─────────────────────────────────────────────────────
        # Step 2: Search Pinecone for top 3 relevant chunks
        # ─────────────────────────────────────────────────────
        logger.info(f"Searching Pinecone for top {RAG_TOP_K} chunks")
        pc = get_pinecone_client()
        index = pc.Index(PINECONE_INDEX)
        
        search_results = index.query(
            vector=query_vector,
            top_k=RAG_TOP_K,
            include_metadata=True,
            namespace="ivy"
        )
        
        # Extract chunks with similarity scores
        context_chunks = []
        for match in search_results.matches:
            chunk_text = match.metadata.get("text", "")
            similarity_score = match.score  # Already 0.0 to 1.0
            context_chunks.append({
                "text": chunk_text,
                "score": similarity_score,
                "source": match.metadata.get("source", "unknown")
            })
            logger.info(f"Retrieved chunk with score {similarity_score:.3f}")
        
        # ─────────────────────────────────────────────────────
        # Step 3: Build context string from chunks
        # ─────────────────────────────────────────────────────
        if context_chunks:
            context_text = "\n\n".join([
                f"[Context {i+1} (relevance: {chunk['score']:.2f})]\n{chunk['text']}"
                for i, chunk in enumerate(context_chunks)
            ])
        else:
            context_text = "[No relevant context found in knowledge base]"
            logger.warning(f"No context found for query: {student_question[:50]}...")
        
        # ─────────────────────────────────────────────────────
        # Step 4: Get conversation history
        # ─────────────────────────────────────────────────────
        conversation_history = get_history(session_id)
        
        # ─────────────────────────────────────────────────────
        # Step 5: Build full prompt
        # ─────────────────────────────────────────────────────
        # Claude API format: system parameter + messages array
        messages = []
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current query with context
        user_message = f"""Context from knowledge base:
{context_text}

Student question: {student_question}"""
        
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # ─────────────────────────────────────────────────────
        # Step 6: Call Claude API with streaming
        # ─────────────────────────────────────────────────────
        logger.info(f"Calling Claude API for session {session_id}")
        client = get_anthropic_client()
        
        full_response = ""
        input_tokens = 0
        output_tokens = 0
        
        async with client.messages.stream(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield text
            
            # Get final message to extract token usage
            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens
        
        # ─────────────────────────────────────────────────────
        # Step 7: Track tokens per session
        # ─────────────────────────────────────────────────────
        total_tokens = input_tokens + output_tokens
        if session_id not in _session_tokens:
            _session_tokens[session_id] = 0
        _session_tokens[session_id] += total_tokens
        
        logger.info(
            f"Session {session_id}: tokens used this call: {total_tokens} "
            f"(input: {input_tokens}, output: {output_tokens}), "
            f"total session tokens: {_session_tokens[session_id]}"
        )
        
        # ─────────────────────────────────────────────────────
        # Step 8: Store conversation in memory
        # ─────────────────────────────────────────────────────
        add_message(session_id, "user", student_question)
        add_message(session_id, "assistant", full_response)
        
    except Exception as e:
        logger.error(f"Error in RAG query service: {e}", exc_info=True)
        error_message = "I apologize, but I'm having trouble processing your question right now. Would you like to speak with one of our expert counsellors for personalised guidance?"
        yield error_message


def get_session_token_usage(session_id: str) -> int:
    """Get total tokens used for a session."""
    return _session_tokens.get(session_id, 0)


def reset_session_tokens(session_id: str) -> None:
    """Reset token counter for a session."""
    if session_id in _session_tokens:
        del _session_tokens[session_id]


def get_all_session_tokens() -> dict[str, int]:
    """Get token usage for all sessions (for monitoring)."""
    return dict(_session_tokens)
