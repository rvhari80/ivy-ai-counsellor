"""OpenAI embedding wrapper for IVY AI Counsellor."""
from openai import AsyncOpenAI
from app.config.settings import settings

_client: AsyncOpenAI | None = None


def get_embedder_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set")
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def embed_text(text: str) -> list[float]:
    """Embed a single text and return vector."""
    client = get_embedder_client()
    r = await client.embeddings.create(input=[text], model=settings.OPENAI_EMBEDDING_MODEL)
    return r.data[0].embedding


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts (batch)."""
    if not texts:
        return []
    client = get_embedder_client()
    r = await client.embeddings.create(input=texts, model=settings.OPENAI_EMBEDDING_MODEL)
    by_idx = {d.index: d.embedding for d in r.data}
    return [by_idx[i] for i in range(len(texts))]
