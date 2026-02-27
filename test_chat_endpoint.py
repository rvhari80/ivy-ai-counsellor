"""Test script for /chat endpoint."""
import asyncio
import json
import httpx


async def test_chat_endpoint():
    """Test the /chat endpoint with streaming response."""
    
    base_url = "http://localhost:8000"
    
    # Test 1: Valid chat request
    print("=" * 60)
    print("Test 1: Valid chat request")
    print("=" * 60)
    
    payload = {
        "session_id": "test_session_001",
        "message": "What are the requirements for studying in Canada?",
        "metadata": {"source": "test"}
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                f"{base_url}/chat",
                json=payload,
                headers={"Accept": "text/event-stream"}
            ) as response:
                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                print("\nStreaming response:")
                print("-" * 60)
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("done"):
                            print(f"\n\n✓ Stream complete. Session: {data.get('session_id')}")
                        else:
                            print(data.get("token", ""), end="", flush=True)
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n")
    
    # Test 2: Empty message (should fail validation)
    print("=" * 60)
    print("Test 2: Empty message validation")
    print("=" * 60)
    
    payload = {
        "session_id": "test_session_002",
        "message": "   ",  # Empty after strip
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{base_url}/chat", json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n")
    
    # Test 3: Message too long (should fail validation)
    print("=" * 60)
    print("Test 3: Message too long validation")
    print("=" * 60)
    
    payload = {
        "session_id": "test_session_003",
        "message": "x" * 501,  # Exceeds 500 char limit
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{base_url}/chat", json=payload)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n")
    
    # Test 4: Rate limiting (send 31 messages rapidly)
    print("=" * 60)
    print("Test 4: Rate limiting (30 messages per hour)")
    print("=" * 60)
    
    session_id = "test_session_rate_limit"
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for i in range(31):
            payload = {
                "session_id": session_id,
                "message": f"Test message {i+1}"
            }
            
            try:
                response = await client.post(f"{base_url}/chat", json=payload)
                if response.status_code == 429:
                    print(f"✓ Message {i+1}: Rate limited (429)")
                    print(f"  Response: {response.json()}")
                    break
                else:
                    print(f"✓ Message {i+1}: Accepted ({response.status_code})")
                    # Consume the stream
                    async with client.stream("POST", f"{base_url}/chat", json=payload) as stream_resp:
                        async for _ in stream_resp.aiter_lines():
                            pass
            except Exception as e:
                print(f"✗ Message {i+1}: Error - {e}")
    
    print("\n")
    
    # Test 5: Check database logging
    print("=" * 60)
    print("Test 5: Database logging verification")
    print("=" * 60)
    print("Check ivy_counsellor.db conversations table for logged entries")
    print("You can run: sqlite3 ivy_counsellor.db 'SELECT * FROM conversations ORDER BY timestamp DESC LIMIT 5;'")
    

if __name__ == "__main__":
    print("\n🚀 Starting /chat endpoint tests...")
    print("Make sure the server is running on http://localhost:8000\n")
    
    asyncio.run(test_chat_endpoint())
    
    print("\n✅ Tests completed!")
