"""Ingest JSONL conversation data into Pinecone."""
import asyncio
import sys
import os
import json
import uuid
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
from app.utils.embedder import embed_texts
from app.models.database import init_db, DB_PATH
import aiosqlite

# ── Config ────────────────────────────────────────────────
JSONL_FILE = "data/jsonl/StudyAbroadGPT-Dataset.jsonl"   # ← your file path
CATEGORY = "sop"                                # ← change per file
COUNTRY = "All"                                 # ← change per file
LAST_UPDATED = "2026-02-28"
PINECONE_NAMESPACE = "ivy"
BATCH_SIZE = 50

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "ivy-counsellor")
# ─────────────────────────────────────────────────────────


def load_jsonl(file_path: str) -> list[dict]:
    """Load all records from JSONL file."""
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Skipping line {line_num} — invalid JSON: {e}")
    return records


def extract_chunks_from_record(record: dict) -> list[dict]:
    """
    Extract text chunks from one JSONL record.
    
    Your format:
    {
      "conversations": [
        {"from": "human", "value": "question..."},
        {"from": "assistant", "value": "answer..."},
        ...
      ]
    }
    
    Strategy: Pair each human+assistant turn as one chunk.
    This preserves Q&A context for better RAG retrieval.
    """
    chunks = []
    conversations = record.get("conversations", [])
    
    # Extract subject from first human message
    subject = ""
    if conversations and conversations[0].get("from") == "human":
        subject = conversations[0].get("value", "")[:100]
    
    # Pair human + assistant messages
    i = 0
    while i < len(conversations) - 1:
        human_msg = conversations[i]
        assistant_msg = conversations[i + 1]
        
        if human_msg.get("from") == "human" and assistant_msg.get("from") == "assistant":
            question = human_msg.get("value", "").strip()
            answer = assistant_msg.get("value", "").strip()
            
            if question and answer:
                # Clean markdown from answer for better embedding
                clean_answer = answer.replace("##", "").replace("**", "").replace("*", "").replace("#", "")
                clean_answer = " ".join(clean_answer.split())  # normalize whitespace
                
                # Combine Q+A as single chunk (better for retrieval)
                combined = f"Question: {question}\n\nAnswer: {clean_answer}"
                
                # Truncate to ~2000 chars to avoid token limits
                if len(combined) > 2000:
                    combined = combined[:2000] + "..."
                
                chunks.append({
                    "text": combined,
                    "question": question[:200],
                    "text_preview": question[:100],
                })
            
            i += 2  # move to next pair
        else:
            i += 1
    
    return chunks


async def ingest_jsonl(
    file_path: str,
    category: str,
    country: str,
    last_updated: str
):
    """Main ingestion function."""
    
    print(f"\n{'='*50}")
    print(f"File:     {file_path}")
    print(f"Category: {category}")
    print(f"Country:  {country}")
    print(f"{'='*50}\n")
    
    # Validate file
    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return
    
    # Load JSONL
    print("Loading JSONL file...")
    records = load_jsonl(file_path)
    print(f"Loaded {len(records)} records")
    
    # Extract all chunks
    print("Extracting Q&A chunks...")
    all_chunks = []
    for record in records:
        chunks = extract_chunks_from_record(record)
        all_chunks.extend(chunks)
    
    print(f"Extracted {len(all_chunks)} chunks")
    
    if not all_chunks:
        print("ERROR: No chunks extracted. Check your JSONL format.")
        return
    
    # Generate PDF/batch ID
    batch_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    
    # Embed in batches
    print(f"\nEmbedding {len(all_chunks)} chunks...")
    texts = [c["text"] for c in all_chunks]
    
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i + BATCH_SIZE]
        batch_embeddings = await embed_texts(batch_texts)
        all_embeddings.extend(batch_embeddings)
        print(f"  Embedded {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")
    
    print(f"Embeddings done ✅")
    
    # Upsert to Pinecone
    print(f"\nUpserting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX)
    
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(all_chunks, all_embeddings)):
        vectors.append({
            "id": f"{batch_id}_{i}",
            "values": embedding,
            "metadata": {
                "pdf_id": batch_id,
                "source_pdf": filename,
                "category": category,
                "country": country,
                "sub_category": category.title(),
                "audience": "Both",
                "last_updated": last_updated,
                "chunk_index": i,
                "text": chunk["text"],
                "text_preview": chunk["text_preview"],
                "question": chunk["question"],
            }
        })
    
    # Upsert in batches of 100
    for i in range(0, len(vectors), 100):
        batch = vectors[i:i + 100]
        index.upsert(vectors=batch, namespace=PINECONE_NAMESPACE)
        print(f"  Upserted {min(i + 100, len(vectors))}/{len(vectors)}")
    
    print(f"Pinecone upsert done ✅")
    
    # Save to SQLite database
    print(f"\nSaving to database...")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO pdf_library 
               (pdf_id, filename, category, chunk_count, status)
               VALUES (?, ?, ?, ?, 'ACTIVE')""",
            (batch_id, filename, category, len(all_chunks))
        )
        await db.commit()
    print(f"Database saved ✅")
    
    # Final summary
    print(f"\n{'='*50}")
    print(f"INGESTION COMPLETE ✅")
    print(f"File:      {filename}")
    print(f"Records:   {len(records)}")
    print(f"Chunks:    {len(all_chunks)}")
    print(f"Batch ID:  {batch_id}")
    print(f"{'='*50}\n")
    
    # Verify
    import time
    time.sleep(3)
    stats = index.describe_index_stats()
    print(f"Pinecone total vectors: {stats.get('total_vector_count', 0)}")
    print(f"Namespaces: {stats.get('namespaces', {})}")


async def main():
    await init_db()
    
    # ── Add your JSONL files here ─────────────────────
    files = [
        {
            "file_path": JSONL_FILE,
            "category": CATEGORY,
            "country": COUNTRY,
            "last_updated": LAST_UPDATED,
        },
        # Add more files:
        # {
        #     "file_path": "data/jsonl/uk_visa.jsonl",
        #     "category": "visa",
        #     "country": "UK",
        #     "last_updated": "2026-02-28",
        # },
    ]
    # ─────────────────────────────────────────────────
    
    for f in files:
        await ingest_jsonl(
            file_path=f["file_path"],
            category=f["category"],
            country=f["country"],
            last_updated=f["last_updated"],
        )

asyncio.run(main())