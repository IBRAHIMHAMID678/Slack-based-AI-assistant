"""ChromaDB local vector store abstraction.

Manages persistent embeddings in cosine distance space with metadata
filtering by industry, source_type, and session_id.
"""

from pathlib import Path
from typing import Any

import chromadb

from app.config import settings
from app.logging import get_logger
from app.rag.embeddings import embed_query, embed_texts

logger = get_logger("chroma_store")

_CHROMA_CLIENT: Any = None
_COLLECTION: Any = None
COLLECTION_NAME = "proposals_knowledge_base"


def get_chroma_client() -> Any:
    """Return singleton persistent Chroma client."""
    global _CHROMA_CLIENT
    if _CHROMA_CLIENT is None:
        persist_path = Path(settings.CHROMA_PERSIST_DIR).resolve()
        persist_path.mkdir(parents=True, exist_ok=True)
        _CHROMA_CLIENT = chromadb.PersistentClient(path=str(persist_path))
    return _CHROMA_CLIENT


def get_collection() -> Any:
    """Return the shared proposals and transcripts Chroma collection."""
    global _COLLECTION
    if _COLLECTION is None:
        client = get_chroma_client()
        _COLLECTION = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _COLLECTION


def add_chunks_to_vector_store(
    chunk_ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """Embed and insert chunks into the Chroma collection."""
    if not chunk_ids:
        return
    collection = get_collection()
    embeddings = embed_texts(documents)
    collection.upsert(
        ids=chunk_ids,
        documents=documents,
        metadatas=metadatas,  # type: ignore
        embeddings=embeddings,  # type: ignore
    )
    logger.info("chunks_upserted_to_vector_store", count=len(chunk_ids))


def query_vector_store(
    query_text: str,
    top_k: int = 5,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Execute cosine similarity search with optional metadata filters."""
    collection = get_collection()
    query_vector = embed_query(query_text)

    query_params: dict[str, Any] = {
        "query_embeddings": [query_vector],
        "n_results": top_k,
    }
    if where:
        query_params["where"] = where

    results: Any = collection.query(**query_params)
    matched_items: list[dict[str, Any]] = []

    if results and results.get("ids") and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            # For cosine space in Chroma, similarity = 1 - distance
            dist = distances[i] if i < len(distances) else 1.0
            similarity = max(0.0, 1.0 - dist)
            matched_items.append(
                {
                    "id": ids[i],
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "score": round(similarity, 4),
                }
            )
    return matched_items
