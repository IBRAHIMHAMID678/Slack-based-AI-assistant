"""FastAPI application entry point and Slack Bolt lifecycle integration.

Configures structured logging, initializes database tables, ingests all 10
proposals at startup, and provides /health and /metrics endpoints.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from app.config import settings
from app.db.migrate import init_db
from app.logging import configure_logging, get_logger
from app.orchestrator.pipeline import ProposalOrchestrator
from app.rag.ingest import ingest_all_proposals
from app.slack.handlers import register_slack_handlers

logger = get_logger("main")

# Initialize Bolt Async App
bolt_app = AsyncApp(
    token=settings.SLACK_BOT_TOKEN,
    signing_secret=settings.SLACK_SIGNING_SECRET,
)

orchestrator = ProposalOrchestrator()
register_slack_handlers(bolt_app, orchestrator)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown lifecycle hooks."""
    configure_logging(settings.LOG_LEVEL)
    logger.info(
        "application_booting",
        environment=settings.ENVIRONMENT,
        mock_mode=settings.is_mock_mode,
    )

    # 1. Initialize SQLite Database Schema
    init_db()

    # 2. Ingest all 10 seed proposals into ChromaDB
    ingest_all_proposals()

    # 3. Start Slack Socket Mode Handler if valid credentials exist
    socket_task = None
    if settings.SLACK_APP_TOKEN.startswith("xapp-") and not settings.SLACK_APP_TOKEN.endswith(
        "mock-token"
    ):
        logger.info("starting_slack_socket_mode_handler")
        handler = AsyncSocketModeHandler(bolt_app, settings.SLACK_APP_TOKEN)
        socket_task = asyncio.create_task(handler.start_async())
    else:
        logger.info("slack_running_in_mock_mode", reason="Mock tokens or mock mode active")

    yield

    if socket_task and not socket_task.done():
        logger.info("shutting_down_slack_socket_handler")
        socket_task.cancel()
        try:
            await socket_task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Slack AI Proposal Assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health_check():
        """Health check endpoint confirming server readiness and operational mode."""
        return {
            "status": "ok",
            "environment": settings.ENVIRONMENT,
            "mock_mode": settings.is_mock_mode,
        }

    return app


app = create_app()
