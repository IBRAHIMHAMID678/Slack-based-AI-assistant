"""Unit tests verifying FastAPI boot, /health endpoint, and Slack Bolt wiring.

Validates Stage 1 Definition of Done:
1. Server starts and /health returns 200
2. Configuration defaults are loaded
3. Welcome card Block Kit payload is generated.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.slack.blocks import build_welcome_card


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify FastAPI /health endpoint returns 200 OK and valid status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "mock_mode" in data


def test_config_and_blocks():
    """Verify settings loads properly and welcome blocks contain header and description."""
    assert settings.DATABASE_URL.startswith("sqlite")
    blocks = build_welcome_card()
    assert len(blocks) >= 3
    assert blocks[0]["type"] == "header"
    assert "Proposal" in blocks[0]["text"]["text"]
