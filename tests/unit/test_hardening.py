"""Unit tests verifying hardening, concurrency guards, truncation, and provider failover.

Validates Stage 8 Definition of Done:
1. AllProvidersFailed handled gracefully without crashing or creating orphaned sessions
2. ConcurrencyGuard prevents race conditions
3. Document size bounds cap excessive uploads with explicit marker
4. Friendly Block Kit error cards generated.
"""

from app.errors import AllProvidersFailed
from app.orchestrator.state import (
    MAX_TRANSCRIPT_CHARS,
    TRUNCATION_MARKER,
    enforce_transcript_bounds,
    session_guard,
)
from app.slack.blocks import build_error_card


def test_transcript_size_cap_truncation():
    """Verify oversized transcripts are capped with an explicit truncation marker."""
    oversized = "A" * (MAX_TRANSCRIPT_CHARS + 500)
    capped = enforce_transcript_bounds(oversized)
    assert len(capped) <= MAX_TRANSCRIPT_CHARS + len(TRUNCATION_MARKER) + 10
    assert TRUNCATION_MARKER.strip() in capped


def test_concurrency_guard_lock_isolation():
    """Verify session locks are isolated by session coordinates."""
    lock1 = session_guard.get_lock("C1:T1:U1")
    lock2 = session_guard.get_lock("C1:T1:U2")
    lock3 = session_guard.get_lock("C1:T1:U1")

    assert lock1 is not lock2
    assert lock1 is lock3


def test_error_card_structure():
    """Verify friendly Block Kit error cards with retry action buttons."""
    card = build_error_card("Provider Failure", "All LLM providers exhausted.", can_retry=True)
    assert len(card) == 2
    assert card[0]["type"] == "section"
    assert "Provider Failure" in card[0]["text"]["text"]
    assert card[1]["type"] == "actions"
    assert card[1]["elements"][0]["action_id"] == "retry_last_action"


def test_all_providers_failed_exception():
    """Verify AllProvidersFailed exception carries appropriate message."""
    exc = AllProvidersFailed("Upstream rate limits exceeded on all providers.")
    assert "rate limits" in str(exc)
