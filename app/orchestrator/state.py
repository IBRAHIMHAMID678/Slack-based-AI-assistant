"""Orchestrator concurrency guards, rate limiting, and transcript limits.

Protects against race conditions, unbounded document uploads, and provides
per-session synchronization locks.
"""

import asyncio

MAX_TRANSCRIPT_CHARS = 500_000
TRUNCATION_MARKER = "\n[TRUNCATED: DOCUMENT EXCEEDED MAXIMUM ALLOWED LENGTH]\n"


class ConcurrencyGuard:
    """Manages asyncio Locks keyed by session coordinates."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, session_key: str) -> asyncio.Lock:
        """Return existing lock or create a new one for session coordinate."""
        if session_key not in self._locks:
            self._locks[session_key] = asyncio.Lock()
        return self._locks[session_key]


def enforce_transcript_bounds(text: str) -> str:
    """Cap document length per prompt and truncate with explicit marker."""
    if not text:
        return ""
    if len(text) > MAX_TRANSCRIPT_CHARS:
        return text[:MAX_TRANSCRIPT_CHARS] + TRUNCATION_MARKER
    return text


session_guard = ConcurrencyGuard()
