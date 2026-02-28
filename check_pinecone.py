"""Check available Pinecone indexes."""
import os
from dotenv import load_dotenv
from pinecone import Pinecone

# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    print("ERROR: PINECONE_API_KEY not found in environment")
    exit(1)

print(f"Using API key: {PINECONE_API_KEY[:10]}...")

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)

# List all indexes
indexes = pc.list_indexes()

print("\nAvailable Pinecone indexes:")
if not indexes:
    print("  No indexes found!")
else:
    for idx in indexes:
        print(f"  - {idx.name}")

print("\nCurrent configuration expects: 'ivy-counsellor'")
