"""Structured logging configuration using structlog.

Enforces JSON formatting with contextual fields (session_id, agent)
bound across async coroutines and workflow steps.
"""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure standard logging and structlog processors for JSON output."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(agent: str = "system", session_id: str = "none") -> structlog.BoundLogger:
    """Return a structlog logger pre-bound with agent and session_id context."""
    return structlog.get_logger().bind(agent=agent, session_id=session_id)
