"""PDF ingestion and chunking for Pinecone."""
import os
import uuid
import logging
import fitz  # PyMuPDF
from pinecone import Pinecone, ServerlessSpec

from app.utils.chunker import chunk_text
from app.utils.embedder import embed_texts
from app.models.database import get_db, DB_PATH
import aiosqlite

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
TOP_K_RESULTS = 3
MAX_FILE_MB = 20
VALID_CATEGORIES = {"visa", "university", "scholarship", "testprep", "finance", "poststudy", "sop"}

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "ivy-counsellor")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")

_namespace = "ivy"
_pc: Pinecone | None = None


def _get_index():
    global _pc
    if _pc is None:
        if not PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY not set")
        _pc = Pinecone(api_key=PINECONE_API_KEY)
    return _pc.Index(PINECONE_INDEX)


def _extract_text_from_pdf(path: str) -> str:
    doc = fitz.open(path)
    text_parts = []
    for page in doc:
        t = page.get_text()
        if not t.strip():
            logger.warning("Scanned/image PDF or empty page - skipping silently")
            continue
        text_parts.append(t)
    doc.close()
    return "\n\n".join(text_parts)


def _chunks_with_meta(text: str, filename: str, category: str) -> list[tuple[str, int, int, str]]:
    """Return (chunk_text, chunk_index, page_number, text_preview). Page number approximated."""
    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    out = []
    for i, c in enumerate(chunks):
        preview = (c[:100] + "…") if len(c) > 100 else c
        out.append((c, i, 1, preview))
    return out


async def ingest_pdf(file_path: str, filename: str, category: str) -> tuple[str, int]:
    """Ingest PDF: chunk, embed, upsert to Pinecone. Returns (pdf_id, chunk_count). Raises on error."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Invalid category. Use one of: {VALID_CATEGORIES}")
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise ValueError(f"File larger than {MAX_FILE_MB}MB")
    text = _extract_text_from_pdf(file_path)
    if not text.strip():
        raise ValueError("Empty PDF or no extractable text")
    chunks_meta = _chunks_with_meta(text, filename, category)
    if not chunks_meta:
        raise ValueError("No chunks produced")
    vectors = await embed_texts([c[0] for c in chunks_meta])
    pdf_id = str(uuid.uuid4())
    index = _get_index()
    for attempt in range(3):
        try:
            upserts = []
            for i, (chunk_text, idx, page, preview) in enumerate(chunks_meta):
                vec = vectors[i] if i < len(vectors) else None
                if vec is None:
                    continue
                upserts.append({
                    "id": f"{pdf_id}_{idx}",
                    "values": vec,
                    "metadata": {
                        "pdf_id": pdf_id,
                        "source_pdf": filename,
                        "category": category,
                        "chunk_index": idx,
                        "page_number": page,
                        "text_preview": preview[:200],
                    },
                })
            index.upsert(vectors=upserts, namespace=_namespace)
            break
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning("Pinecone upsert retry %s: %s", attempt + 1, e)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO pdf_library (pdf_id, filename, category, chunk_count, status)
               VALUES (?, ?, ?, ?, 'ACTIVE')""",
            (pdf_id, filename, category, len(chunks_meta)),
        )
        await db.commit()
    return pdf_id, len(chunks_meta)


async def delete_pdf_from_index(pdf_id: str) -> None:
    """Delete all vectors for this pdf_id from Pinecone (by metadata filter if supported)."""
    index = _get_index()
    # Pinecone delete by metadata filter
    try:
        index.delete(filter={"pdf_id": {"$eq": pdf_id}}, namespace=_namespace)
    except Exception as e:
        logger.warning("Pinecone delete by filter failed: %s", e)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE pdf_library SET status = 'DELETED' WHERE pdf_id = ?", (pdf_id,))
        await db.commit()
