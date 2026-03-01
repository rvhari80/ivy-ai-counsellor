"""Tiktoken-based text splitter for ... chunks."""
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
    chunks = []

    # Split into paragraphs first to avoid encoding entire text at once
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_tokens = []

    for paragraph in paragraphs:
        # Encode one paragraph at a time (avoids MemoryError)
        para_tokens = enc.encode(paragraph[:2000])  # cap per paragraph

        # If paragraph alone exceeds chunk size, split it directly
        if len(para_tokens) > chunk_size:
            # Flush current first
            if current_tokens:
                chunks.append(enc.decode(current_tokens))
                current_tokens = current_tokens[-overlap:] if overlap else []

            # Split large paragraph
            start = 0
            while start < len(para_tokens):
                end = min(start + chunk_size, len(para_tokens))
                chunks.append(enc.decode(para_tokens[start:end]))
                start = end - overlap
                if start >= len(para_tokens):
                    break
            continue

        # Adding paragraph exceeds chunk size — flush first
        if len(current_tokens) + len(para_tokens) > chunk_size:
            if current_tokens:
                chunks.append(enc.decode(current_tokens))
                current_tokens = current_tokens[-overlap:] if overlap else []

        current_tokens.extend(para_tokens)

    # Flush remaining
    if current_tokens:
        chunks.append(enc.decode(current_tokens))

    return [c for c in chunks if c.strip()]