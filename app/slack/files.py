"""File handling utilities for Slack transcripts and generated documents.

Manages downloading uploaded transcripts from Slack and delivering
generated proposal DOCX files back into Slack threads.
"""

from io import BytesIO
from typing import Any

import httpx
from slack_sdk.web.async_client import AsyncWebClient

from app.errors import SlackInteractionError
from app.logging import get_logger

logger = get_logger("slack_files")


async def download_slack_file(url: str, token: str) -> str:
    """Download text content from private Slack file download URL.

    Args:
        url: Private URL provided in Slack file payload.
        token: Bot token (xoxb-...) for authorization.

    Returns:
        The text content of the downloaded file.
    """
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            logger.error("slack_file_download_failed", status=response.status_code, url=url)
            raise SlackInteractionError(
                f"Failed to download Slack file: HTTP {response.status_code}"
            )
        return response.text


async def upload_docx_to_thread(
    client: AsyncWebClient,
    channel_id: str,
    thread_ts: str,
    file_content: bytes | BytesIO,
    filename: str,
    initial_comment: str,
) -> dict[str, Any]:
    """Upload a generated proposal DOCX file to a specific Slack thread.

    Uses the modern Slack files_upload_v2 API.
    """
    try:
        content_bytes = (
            file_content.getvalue() if isinstance(file_content, BytesIO) else file_content
        )
        response = await client.files_upload_v2(
            channel=channel_id,
            thread_ts=thread_ts,
            file=content_bytes,
            filename=filename,
            title=filename,
            initial_comment=initial_comment,
        )
        logger.info(
            "docx_uploaded_to_slack",
            channel=channel_id,
            thread_ts=thread_ts,
            filename=filename,
        )
        return getattr(response, "data", {})
    except Exception as exc:
        logger.error("docx_upload_failed", error=str(exc))
        raise SlackInteractionError(f"Failed to upload proposal DOCX to Slack: {exc}") from exc
