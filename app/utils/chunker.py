"""Tiktoken-based text splitter for PDF chunks."""
import tiktoken

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50


def get_encoder():
    try:
        return tiktoken.encoding_for_model("gpt-4")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks by token count with overlap."""
    if not text or not text.strip():
        return []
    enc = get_encoder()
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        start = end - overlap
        if start >= len(tokens):
            break
    return chunks
