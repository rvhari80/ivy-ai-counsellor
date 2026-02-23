"""
PDF Ingestion Service for IVY AI Counsellor.

This service handles the complete pipeline for ingesting PDF documents into the
knowledge base:
1. Extract text from PDF (PyMuPDF/fitz)
2. Chunk text using tiktoken (512 tokens, 50 overlap)
3. Generate embeddings (OpenAI text-embedding-3-small)
4. Store vectors in Pinecone with metadata
5. Save metadata to SQLite database
"""
import os
import uuid
import time
import logging
from typing import NamedTuple
from pathlib import Path

import fitz  # PyMuPDF
import tiktoken
from pinecone import Pinecone
import aiosqlite

from app.utils.chunker import chunk_text
from app.utils.embedder import embed_texts
from app.models.database import DB_PATH
from app.config.settings import settings
from app.core.exceptions import PDFProcessingException

logger = logging.getLogger(__name__)

# Constants
CHUNK_SIZE = 512  # tokens
CHUNK_OVERLAP = 50  # tokens
MAX_FILE_MB = 50
VALID_CATEGORIES = {"visa", "university", "scholarship", "testprep", "finance", "poststudy", "sop"}
PINECONE_NAMESPACE = "ivy"
BATCH_SIZE = 100  # Pinecone batch size

# Global Pinecone client (lazy initialization)
_pinecone_client: Pinecone | None = None


class PageContent(NamedTuple):
    """Represents extracted content from a single page."""
    page_number: int
    text: str
    is_empty: bool
    is_scanned: bool


class ChunkMetadata(NamedTuple):
    """Represents metadata for a text chunk."""
    chunk_text: str
    chunk_index: int
    page_number: int
    text_preview: str


class IngestionSummary(NamedTuple):
    """Summary of PDF ingestion results."""
    pdf_id: str
    filename: str
    category: str
    total_pages: int
    pages_processed: int
    pages_skipped: int
    total_chunks: int
    time_taken_seconds: float
    success: bool
    error: str | None = None


def _get_pinecone_index():
    """
    Get or create Pinecone index instance.
    Uses lazy initialization and caches the client.
    """
    global _pinecone_client

    if _pinecone_client is None:
        if not settings.PINECONE_API_KEY:
            raise PDFProcessingException("PINECONE_API_KEY not configured")
        _pinecone_client = Pinecone(api_key=settings.PINECONE_API_KEY)

    return _pinecone_client.Index(settings.PINECONE_INDEX)


def _extract_page_content(page: fitz.Page, page_num: int) -> PageContent:
    """
    Extract text from a single PDF page.

    Detects:
    - Empty pages (no text)
    - Scanned/image-only pages (very little text relative to page size)

    Args:
        page: PyMuPDF page object
        page_num: Page number (1-indexed)

    Returns:
        PageContent with extracted text and metadata
    """
    try:
        text = page.get_text()

        # Check if page is empty
        if not text or not text.strip():
            logger.debug(f"Page {page_num}: Empty page detected")
            return PageContent(
                page_number=page_num,
                text="",
                is_empty=True,
                is_scanned=False
            )

        # Check if page is scanned/image-only
        # Heuristic: if text is very short relative to page size, likely scanned
        word_count = len(text.split())
        is_likely_scanned = word_count < 10  # Less than 10 words likely scanned

        if is_likely_scanned:
            logger.debug(f"Page {page_num}: Scanned/image-only page detected ({word_count} words)")
            return PageContent(
                page_number=page_num,
                text="",
                is_empty=False,
                is_scanned=True
            )

        # Clean text: remove excessive whitespace
        cleaned_text = " ".join(text.split())

        return PageContent(
            page_number=page_num,
            text=cleaned_text,
            is_empty=False,
            is_scanned=False
        )

    except Exception as e:
        logger.warning(f"Error extracting text from page {page_num}: {e}")
        return PageContent(
            page_number=page_num,
            text="",
            is_empty=True,
            is_scanned=False
        )


def _extract_text_from_pdf(file_path: str) -> tuple[str, dict]:
    """
    Extract text from PDF file page by page.

    Args:
        file_path: Path to PDF file

    Returns:
        Tuple of (combined_text, stats_dict)
        stats_dict contains: total_pages, pages_processed, pages_skipped, etc.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise PDFProcessingException(f"Failed to open PDF: {e}")

    page_contents = []
    stats = {
        "total_pages": len(doc),
        "pages_processed": 0,
        "pages_empty": 0,
        "pages_scanned": 0,
    }

    # Extract text from each page
    for page_num, page in enumerate(doc, start=1):
        content = _extract_page_content(page, page_num)

        if content.is_empty:
            stats["pages_empty"] += 1
        elif content.is_scanned:
            stats["pages_scanned"] += 1
        else:
            page_contents.append(content)
            stats["pages_processed"] += 1

    doc.close()

    # Combine all page texts
    combined_text = "\n\n".join(
        f"[Page {pc.page_number}]\n{pc.text}"
        for pc in page_contents
    )

    stats["pages_skipped"] = stats["pages_empty"] + stats["pages_scanned"]

    logger.info(
        f"PDF extraction complete: {stats['total_pages']} total pages, "
        f"{stats['pages_processed']} processed, {stats['pages_skipped']} skipped "
        f"({stats['pages_empty']} empty, {stats['pages_scanned']} scanned)"
    )

    return combined_text, stats


def _create_chunks_with_metadata(
    text: str,
    filename: str,
    category: str
) -> list[ChunkMetadata]:
    """
    Chunk text using tiktoken and create metadata for each chunk.

    Args:
        text: Combined text from PDF
        filename: Original filename
        category: Document category

    Returns:
        List of ChunkMetadata objects
    """
    # Chunk text using tiktoken (512 tokens, 50 overlap)
    chunks = chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

    if not chunks:
        logger.warning("No chunks produced from text")
        return []

    chunk_metadata_list = []

    for idx, chunk in enumerate(chunks):
        # Extract page number from chunk (if available)
        # Format: [Page X]\n...
        page_number = 1  # Default
        if chunk.startswith("[Page "):
            try:
                page_end = chunk.find("]")
                if page_end > 0:
                    page_str = chunk[6:page_end]
                    page_number = int(page_str)
            except (ValueError, IndexError):
                pass

        # Create text preview (first 100 chars)
        text_preview = chunk[:100]
        if len(chunk) > 100:
            text_preview += "..."

        chunk_metadata_list.append(
            ChunkMetadata(
                chunk_text=chunk,
                chunk_index=idx,
                page_number=page_number,
                text_preview=text_preview
            )
        )

    logger.info(f"Created {len(chunk_metadata_list)} chunks from text")
    return chunk_metadata_list


async def _upsert_to_pinecone(
    pdf_id: str,
    chunks: list[ChunkMetadata],
    embeddings: list[list[float]],
    filename: str,
    category: str
) -> None:
    """
    Upsert chunk embeddings to Pinecone in batches.

    Args:
        pdf_id: Unique PDF identifier
        chunks: List of chunk metadata
        embeddings: List of embedding vectors
        filename: Original filename
        category: Document category
    """
    if len(chunks) != len(embeddings):
        raise PDFProcessingException(
            f"Mismatch between chunks ({len(chunks)}) and embeddings ({len(embeddings)})"
        )

    index = _get_pinecone_index()

    # Prepare upsert data
    vectors_to_upsert = []
    for chunk, embedding in zip(chunks, embeddings):
        vectors_to_upsert.append({
            "id": f"{pdf_id}_{chunk.chunk_index}",
            "values": embedding,
            "metadata": {
                "pdf_id": pdf_id,
                "source_pdf": filename,
                "category": category,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "text_preview": chunk.text_preview,
            }
        })

    # Upsert in batches (Pinecone has limits)
    total_upserted = 0
    for i in range(0, len(vectors_to_upsert), BATCH_SIZE):
        batch = vectors_to_upsert[i:i + BATCH_SIZE]

        # Retry logic for Pinecone
        for attempt in range(3):
            try:
                index.upsert(vectors=batch, namespace=PINECONE_NAMESPACE)
                total_upserted += len(batch)
                logger.debug(f"Upserted batch {i // BATCH_SIZE + 1}: {len(batch)} vectors")
                break
            except Exception as e:
                if attempt == 2:  # Last attempt
                    raise PDFProcessingException(f"Failed to upsert to Pinecone after 3 attempts: {e}")
                logger.warning(f"Pinecone upsert attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(1)  # Wait before retry

    logger.info(f"Successfully upserted {total_upserted} vectors to Pinecone")


async def _save_to_database(
    pdf_id: str,
    filename: str,
    category: str,
    chunk_count: int
) -> None:
    """
    Save PDF metadata to SQLite database.

    Args:
        pdf_id: Unique PDF identifier
        filename: Original filename
        category: Document category
        chunk_count: Number of chunks created
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO pdf_library (pdf_id, filename, category, chunk_count, status)
               VALUES (?, ?, ?, ?, 'ACTIVE')""",
            (pdf_id, filename, category, chunk_count)
        )
        await db.commit()

    logger.info(f"Saved PDF metadata to database: {pdf_id}")


async def ingest_pdf(
    file_path: str,
    filename: str,
    category: str
) -> IngestionSummary:
    """
    Complete PDF ingestion pipeline.

    This function:
    1. Validates file and category
    2. Extracts text from PDF (skips empty/scanned pages)
    3. Chunks text using tiktoken (512 tokens, 50 overlap)
    4. Generates embeddings using OpenAI
    5. Stores vectors in Pinecone with metadata
    6. Saves metadata to database
    7. Returns detailed ingestion summary

    Args:
        file_path: Path to PDF file
        filename: Original filename
        category: Document category (visa/university/scholarship/etc.)

    Returns:
        IngestionSummary with detailed results

    Raises:
        PDFProcessingException: If ingestion fails
    """
    start_time = time.time()

    # Validate category
    if category not in VALID_CATEGORIES:
        raise PDFProcessingException(
            f"Invalid category '{category}'. Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    # Validate file exists
    if not os.path.exists(file_path):
        raise PDFProcessingException(f"File not found: {file_path}")

    # Validate file size
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise PDFProcessingException(
            f"File too large: {size_mb:.2f}MB (max: {MAX_FILE_MB}MB)"
        )

    logger.info(f"Starting PDF ingestion: {filename} ({size_mb:.2f}MB, category: {category})")

    try:
        # Step 1: Extract text from PDF
        text, extraction_stats = _extract_text_from_pdf(file_path)

        if not text or not text.strip():
            raise PDFProcessingException(
                "No extractable text found in PDF. "
                "File may be scanned/image-only or empty."
            )

        # Step 2: Chunk text
        chunks = _create_chunks_with_metadata(text, filename, category)

        if not chunks:
            raise PDFProcessingException("Failed to create chunks from text")

        # Step 3: Generate embeddings
        logger.info(f"Generating embeddings for {len(chunks)} chunks...")
        chunk_texts = [chunk.chunk_text for chunk in chunks]
        embeddings = await embed_texts(chunk_texts)

        if len(embeddings) != len(chunks):
            raise PDFProcessingException(
                f"Embedding count mismatch: {len(embeddings)} embeddings for {len(chunks)} chunks"
            )

        # Step 4: Generate unique PDF ID
        pdf_id = str(uuid.uuid4())

        # Step 5: Upsert to Pinecone
        logger.info(f"Upserting {len(chunks)} vectors to Pinecone...")
        await _upsert_to_pinecone(pdf_id, chunks, embeddings, filename, category)

        # Step 6: Save to database
        await _save_to_database(pdf_id, filename, category, len(chunks))

        # Calculate time taken
        time_taken = time.time() - start_time

        logger.info(
            f"PDF ingestion complete: {filename} | "
            f"{len(chunks)} chunks | {time_taken:.2f}s"
        )

        return IngestionSummary(
            pdf_id=pdf_id,
            filename=filename,
            category=category,
            total_pages=extraction_stats["total_pages"],
            pages_processed=extraction_stats["pages_processed"],
            pages_skipped=extraction_stats["pages_skipped"],
            total_chunks=len(chunks),
            time_taken_seconds=round(time_taken, 2),
            success=True,
            error=None
        )

    except PDFProcessingException:
        # Re-raise PDF processing exceptions
        raise

    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error during PDF ingestion: {e}", exc_info=True)
        raise PDFProcessingException(f"PDF ingestion failed: {str(e)}")


async def delete_pdf_from_index(pdf_id: str) -> bool:
    """
    Delete all vectors for a PDF from Pinecone and mark as deleted in database.

    Args:
        pdf_id: Unique PDF identifier

    Returns:
        True if successful, False otherwise
    """
    try:
        index = _get_pinecone_index()

        # Delete from Pinecone using metadata filter
        index.delete(
            filter={"pdf_id": {"$eq": pdf_id}},
            namespace=PINECONE_NAMESPACE
        )
        logger.info(f"Deleted PDF vectors from Pinecone: {pdf_id}")

        # Mark as deleted in database
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE pdf_library SET status = 'DELETED' WHERE pdf_id = ?",
                (pdf_id,)
            )
            await db.commit()

        logger.info(f"Marked PDF as deleted in database: {pdf_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete PDF {pdf_id}: {e}", exc_info=True)
        return False


async def list_pdfs() -> list[dict]:
    """
    List all PDFs in the knowledge base.

    Returns:
        List of PDF metadata dictionaries
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT pdf_id, filename, category, chunk_count, status, upload_date
               FROM pdf_library
               WHERE status = 'ACTIVE'
               ORDER BY upload_date DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
