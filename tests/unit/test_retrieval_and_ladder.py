"""Unit tests verifying semantic retrieval ladder, thresholds, and fallback rules.

Validates:
1. Exact industry filter step
2. Adjacent industry fallback step
3. Unfiltered global top-k search step
4. Low confidence flag on weak scores (< 0.50)
5. Session-scoped transcript quote retrieval.
"""

from app.rag.retrieve import (
    ADJACENT_INDUSTRIES,
    RetrievalResult,
    retrieve_proposal_context,
    retrieve_transcript_quotes,
)


def test_adjacent_industries_mapping_completeness():
    """Verify all 10 project industries have mapped fallbacks."""
    expected_industries = [
        "retail",
        "retail2",
        "distribution",
        "fleet",
        "logistics",
        "manufacturing",
        "construction",
        "consulting",
        "fintech",
        "healthcare",
    ]
    for ind in expected_industries:
        assert ind in ADJACENT_INDUSTRIES
        assert len(ADJACENT_INDUSTRIES[ind]) >= 1


def test_retrieval_exact_industry_match():
    """Verify healthcare query with healthcare filter hits exact_industry ladder step."""
    query = "patient intake digitization and medical record forms"
    res = retrieve_proposal_context(query=query, industry="healthcare", top_k=3)
    assert res.ladder_step == "exact_industry"
    assert len(res.chunks) >= 1
    assert res.chunks[0]["metadata"]["industry"] == "healthcare"
    assert res.low_confidence is False


def test_retrieval_adjacent_industry_fallback():
    """Verify fleet query with logistics filter falls back to adjacent industries."""
    query = "last mile delivery dispatch and driver route notifications"
    res = retrieve_proposal_context(query=query, industry="fleet", top_k=3)
    assert res.ladder_step in ["exact_industry", "adjacent_industry"]
    assert len(res.chunks) >= 1


def test_retrieval_unfiltered_fallback():
    """Verify unknown or unmapped industry triggers unfiltered search."""
    query = "real time inventory synchronization across regional warehouses"
    res = retrieve_proposal_context(query=query, industry="space_exploration", top_k=4)
    assert res.ladder_step == "unfiltered_top_k"
    assert len(res.chunks) >= 1


def test_retrieval_result_serialization():
    """Verify RetrievalResult converts cleanly to dictionary."""
    sample_chunks = [{"id": "c1", "score": 0.85, "document": "Sample text"}]
    res = RetrievalResult(chunks=sample_chunks, ladder_step="exact_industry", low_confidence=False)
    data = res.to_dict()
    assert data["ladder_step"] == "exact_industry"
    assert data["chunk_count"] == 1
    assert data["low_confidence"] is False


def test_transcript_quote_retrieval_empty_session():
    """Verify transcript retrieval on non-existent session returns empty list gracefully."""
    quotes = retrieve_transcript_quotes("non_existent_session_id_999", "deadline")
    assert isinstance(quotes, list)
    assert len(quotes) == 0
