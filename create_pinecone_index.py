"""Create the Pinecone index for IVY AI Counsellor."""
import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "ivy-counsellor")

if not PINECONE_API_KEY:
    print("ERROR: PINECONE_API_KEY not found in environment")
    exit(1)

print(f"Creating Pinecone index: {PINECONE_INDEX}")
print(f"Using API key: {PINECONE_API_KEY[:10]}...")

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)

# Check if index already exists
existing_indexes = [idx.name for idx in pc.list_indexes()]
if PINECONE_INDEX in existing_indexes:
    print(f"\n[OK] Index '{PINECONE_INDEX}' already exists!")
    exit(0)

# Create the index
# OpenAI text-embedding-3-small produces 1536-dimensional vectors
print(f"\nCreating index '{PINECONE_INDEX}'...")
print("  - Dimension: 1536 (OpenAI text-embedding-3-small)")
print("  - Metric: cosine")
print("  - Cloud: AWS")
print("  - Region: us-east-1")

try:
    pc.create_index(
        name=PINECONE_INDEX,
        dimension=1536,  # OpenAI text-embedding-3-small dimension
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    print(f"\n[SUCCESS] Successfully created index '{PINECONE_INDEX}'!")
    print("\nNote: It may take a few moments for the index to be fully initialized.")
    print("You can check the status in your Pinecone dashboard.")
    
except Exception as e:
    print(f"\n[ERROR] Error creating index: {e}")
    print("\nPlease check:")
    print("  1. Your Pinecone API key is valid")
    print("  2. You have permission to create indexes")
    print("  3. Your Pinecone plan supports the selected cloud/region")
    exit(1)
