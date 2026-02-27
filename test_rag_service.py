"""Test script for RAG service."""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the RAG service
from app.services.rag_service import query_rag, get_session_token_usage


async def test_rag_service():
    """Test the RAG query service."""
    print("=" * 60)
    print("Testing RAG Query Service")
    print("=" * 60)
    
    # Test query
    test_question = "What are the requirements for studying in Canada?"
    test_session_id = "test_session_123"
    
    print(f"\nQuestion: {test_question}")
    print(f"Session ID: {test_session_id}")
    print("\nStreaming response:")
    print("-" * 60)
    
    try:
        # Stream the response
        async for token in query_rag(test_question, test_session_id):
            print(token, end="", flush=True)
        
        print("\n" + "-" * 60)
        
        # Check token usage
        tokens_used = get_session_token_usage(test_session_id)
        print(f"\nTotal tokens used in session: {tokens_used}")
        
        print("\n✅ RAG service test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_rag_service())
