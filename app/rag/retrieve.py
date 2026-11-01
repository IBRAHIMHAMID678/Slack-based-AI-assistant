"""Semantic retrieval engine with multi-stage fallback ladder.

Executes meaning-based vector search against ChromaDB using:
1. Exact industry filter
2. Adjacent industry filter
3. Unfiltered global top-k search
4. Low-confidence threshold flagging (< 0.50).
"""

from typing import Any

from app.logging import get_logger
from app.rag.store import query_vector_store

logger = get_logger("retrieval_ladder")

CONFIDENCE_THRESHOLD = 0.65
LOW_CONFIDENCE_CUTOFF = 0.50

ADJACENT_INDUSTRIES: dict[str, list[str]] = {
    "retail": ["retail2", "distribution", "logistics"],
    "retail2": ["retail", "distribution", "logistics"],
    "distribution": ["logistics", "fleet", "retail"],
    "fleet": ["logistics", "distribution"],
    "logistics": ["fleet", "distribution", "manufacturing"],
    "manufacturing": ["logistics", "construction"],
    "construction": ["manufacturing", "consulting"],
    "consulting": ["fintech", "construction"],
    "fintech": ["consulting", "retail"],
    "healthcare": ["consulting"],
}


class RetrievalResult:
    """Encapsulates retrieval outputs, metadata citations, and confidence status."""

    def __init__(
        self,
        chunks: list[dict[str, Any]],
        ladder_step: str,
        low_confidence: bool = False,
    ) -> None:
        self.chunks = chunks
        self.ladder_step = ladder_step
        self.low_confidence = low_confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert result object to dictionary."""
        return {
            "ladder_step": self.ladder_step,
            "low_confidence": self.low_confidence,
            "chunk_count": len(self.chunks),
            "chunks": self.chunks,
        }


def retrieve_proposal_context(
    query: str,
    industry: str | None = None,
    top_k: int = 4,
) -> RetrievalResult:
    """Retrieve relevant proposal context following the 4-step fallback ladder."""
    target_ind = (industry or "").lower().strip()

    # Step 1: Exact Industry Filter
    if target_ind and target_ind != "unspecified":
        logger.info("retrieval_ladder_step_1_exact", industry=target_ind)
        matches = query_vector_store(
            query_text=query,
            top_k=top_k,
            where={"industry": target_ind},
        )
        if matches and matches[0]["score"] >= CONFIDENCE_THRESHOLD:
            return RetrievalResult(matches, ladder_step="exact_industry", low_confidence=False)

    # Step 2: Adjacent Industry Filter
    adjacent = ADJACENT_INDUSTRIES.get(target_ind, [])
    if adjacent:
        logger.info("retrieval_ladder_step_2_adjacent", adjacent=adjacent)
        # Chroma supports $in operator for lists
        adjacent_filter = {"industry": {"$in": adjacent}}
        matches = query_vector_store(
            query_text=query,
            top_k=top_k,
            where=adjacent_filter,
        )
        if matches and matches[0]["score"] >= CONFIDENCE_THRESHOLD:
            return RetrievalResult(matches, ladder_step="adjacent_industry", low_confidence=False)

    # Step 3: Unfiltered Semantic Top-K (proposals only)
    logger.info("retrieval_ladder_step_3_unfiltered", query=query)
    unfiltered_matches = query_vector_store(
        query_text=query,
        top_k=top_k,
        where={"source_type": "proposal"},
    )

    if not unfiltered_matches:
        logger.warning("retrieval_empty_results", query=query)
        return RetrievalResult([], ladder_step="empty", low_confidence=True)

    top_score = unfiltered_matches[0]["score"]
    is_low_conf = top_score < LOW_CONFIDENCE_CUTOFF

    if is_low_conf:
        logger.warning("retrieval_low_confidence", top_score=top_score, query=query)

    return RetrievalResult(
        unfiltered_matches,
        ladder_step="unfiltered_top_k",
        low_confidence=is_low_conf,
    )


def retrieve_transcript_quotes(
    session_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve exact quotes from the session's uploaded transcript."""
    return query_vector_store(
        query_text=query,
        top_k=top_k,
        where={"$and": [{"source_type": "transcript"}, {"session_id": session_id}]},
    )
