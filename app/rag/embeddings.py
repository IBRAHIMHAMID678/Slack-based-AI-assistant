"""Local sentence-transformers embeddings integration.

Uses BAAI/bge-small-en-v1.5 with CPU execution and L2 normalization
for cosine distance retrieval in ChromaDB.
"""

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.logging import get_logger

logger = get_logger("embeddings")

_EMBEDDER_INSTANCE: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Return singleton instance of the local SentenceTransformer embedding model."""
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        logger.info("loading_local_embedding_model", model=settings.EMBEDDING_MODEL_NAME)
        _EMBEDDER_INSTANCE = SentenceTransformer(
            settings.EMBEDDING_MODEL_NAME,
            device="cpu",
        )
        logger.info("embedding_model_loaded_successfully")
    return _EMBEDDER_INSTANCE


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate L2-normalized dense embeddings for a list of text chunks.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of 384-dimensional normalized float vectors.
    """
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embeddings.tolist()  # type: ignore


def embed_query(query: str) -> list[float]:
    """Generate L2-normalized dense embedding for a single search query."""
    model = get_embedding_model()
    # BGE models benefit from instruction prefix on queries
    prefix = "Represent this sentence for searching relevant passages: "
    query_text = f"{prefix}{query.strip()}"
    embedding = model.encode(
        query_text,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return embedding.tolist()  # type: ignore
