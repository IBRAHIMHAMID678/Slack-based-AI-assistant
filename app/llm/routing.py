"""Model routing configuration and provider failover definitions.

Maps task categories to primary (Groq) and fallback (OpenRouter) models
with predefined temperature settings.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskRoute:
    """Routing specification for a given LLM task."""

    primary_provider: str
    primary_model: str
    fallback_provider: str
    fallback_model: str
    temperature: float


ROUTING_TABLE: dict[str, TaskRoute] = {
    "intake_extract": TaskRoute(
        primary_provider="groq",
        primary_model="llama-3.3-70b-versatile",
        fallback_provider="openrouter",
        fallback_model="meta-llama/llama-3.3-70b-instruct:free",
        temperature=0.1,
    ),
    "writer_section": TaskRoute(
        primary_provider="groq",
        primary_model="llama-3.3-70b-versatile",
        fallback_provider="openrouter",
        fallback_model="meta-llama/llama-3.3-70b-instruct:free",
        temperature=0.3,
    ),
    "critic_review": TaskRoute(
        primary_provider="groq",
        primary_model="llama-3.3-70b-versatile",
        fallback_provider="openrouter",
        fallback_model="meta-llama/llama-3.3-70b-instruct:free",
        temperature=0.1,
    ),
    "section_router": TaskRoute(
        primary_provider="groq",
        primary_model="llama-3.1-8b-instant",
        fallback_provider="openrouter",
        fallback_model="meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.1,
    ),
    "query_rewrite": TaskRoute(
        primary_provider="groq",
        primary_model="llama-3.1-8b-instant",
        fallback_provider="openrouter",
        fallback_model="meta-llama/llama-3.1-8b-instruct:free",
        temperature=0.1,
    ),
}
