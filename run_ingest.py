"""Run PDF ingestion into Pinecone."""
import asyncio
import sys
import os
sys.path.append(".")

from dotenv import load_dotenv
load_dotenv()

from app.models.database import init_db
from app.services.pdf_service import ingest_pdf


async def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    pdfs = [
        (os.path.join(BASE_DIR, "data", "pdfs", "australia_visa.pdf"), "australia_visa.pdf", "visa"),
    ]
    await init_db()
    for file_path, filename, category in pdfs:
        if not os.path.exists(file_path):
            print(f"SKIP — file not found: {file_path}")
            continue
        print(f"\nIngesting: {filename} [{category}]...")
        try:
            summary = await ingest_pdf(file_path, filename, category)
            print(f"  Done ✅")
            print(f"  PDF ID:    {summary.pdf_id}")
            print(f"  Pages:     {summary.pages_processed}/{summary.total_pages}")
            print(f"  Chunks:    {summary.total_chunks}")
            print(f"  Time:      {summary.time_taken_seconds}s")
        except Exception as e:
            print(f"  FAILED ❌  {e}")
    print("\nAll done.")


asyncio.run(main())