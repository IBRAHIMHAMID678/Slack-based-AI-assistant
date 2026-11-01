"""Application-wide custom exception definitions.

This module defines domain-specific error hierarchies for LLM failover,
data validation, agent workflow execution, retrieval, and document generation.
"""


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LLMProviderError(AppError):
    """Raised when an individual LLM provider encounters a 4xx/5xx or timeout."""

    def __init__(self, provider: str, status_code: int | None, message: str) -> None:
        super().__init__(
            f"Provider '{provider}' failed with status {status_code}: {message}",
            {"provider": provider, "status_code": status_code, "raw_message": message},
        )
        self.provider = provider
        self.status_code = status_code


class AllProvidersFailed(AppError):
    """Raised when all configured LLM providers in the fallback chain fail."""

    def __init__(self, message: str = "All LLM providers in the failover chain failed.") -> None:
        super().__init__(message)


class SchemaValidationError(AppError):
    """Raised when LLM output violates the expected Pydantic schema."""

    def __init__(self, message: str, errors: list | None = None) -> None:
        super().__init__(message, {"validation_errors": errors or []})
        self.errors = errors or []


class SessionNotFoundError(AppError):
    """Raised when a session identifier cannot be resolved in persistence."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"Session '{session_id}' not found.", {"session_id": session_id})
        self.session_id = session_id


class RetrievalError(AppError):
    """Raised when semantic retrieval or vector search fails."""


class IngestionError(AppError):
    """Raised when file chunking or vector store indexing encounters an error."""


class DocxRenderError(AppError):
    """Raised when python-docx generation or file serialization fails."""


class SlackInteractionError(AppError):
    """Raised when Slack API calls or webhook interactions fail."""
