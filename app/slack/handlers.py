"""Slack event listeners and interaction action handlers.

Connects Slack Bolt Socket Mode events (app mentions, DMs, file uploads,
button actions, and modals) to the multi-agent pipeline orchestrator.
"""

import time
from typing import Any

_PROCESSED_FILE_IDS: dict[str, float] = {}

from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from app.logging import get_logger
from app.slack.blocks import (
    build_error_card,
    build_welcome_card,
)
from app.slack.modals import build_regenerate_section_modal

logger = get_logger("slack_handlers")


def register_slack_handlers(bolt_app: AsyncApp, orchestrator: Any) -> None:
    """Register all Slack Bolt event listeners, actions, and modal views."""

    @bolt_app.event("app_mention")
    async def handle_app_mention(event: dict[str, Any], say: Any, client: Any) -> None:
        """Handle when the bot is directly mentioned."""
        channel_id = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")
        user_id = event.get("user", "")
        text = event.get("text", "").strip()

        logger.info("app_mention_received", channel=channel_id, user=user_id, text=text)

        # Check if text contains a follow-up question on an existing session
        clean_text = text.split(">", 1)[-1].strip() if ">" in text else text
        if not clean_text or clean_text.lower() in ["help", "hi", "hello", "invite"]:
            await say(blocks=build_welcome_card(), thread_ts=thread_ts)
            return

        try:
            # Process conversational follow-up via orchestrator
            response = await orchestrator.handle_user_message(
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                message_text=clean_text,
                client=client,
            )
            await say(text=response, thread_ts=thread_ts)
        except Exception as exc:
            logger.error("error_handling_mention", error=str(exc))
            await say(
                blocks=build_error_card("Error Processing Request", str(exc)),
                thread_ts=thread_ts,
            )

    @bolt_app.event("file_shared")
    async def handle_file_shared_event(event: dict[str, Any], client: Any) -> None:
        """Handle when a file is uploaded to a channel or DM where the bot is present."""
        file_id = event.get("file_id")
        channel_id = event.get("channel_id", "")
        user_id = event.get("user_id", "")

        logger.info("file_shared_event_received", file_id=file_id, channel=channel_id, user=user_id)
        if not file_id:
            return

        now = time.time()
        # Clean up stale entries older than 5 minutes
        stale_keys = [k for k, ts in _PROCESSED_FILE_IDS.items() if now - ts > 300.0]
        for k in stale_keys:
            _PROCESSED_FILE_IDS.pop(k, None)

        if file_id in _PROCESSED_FILE_IDS and (now - _PROCESSED_FILE_IDS[file_id]) < 60.0:
            logger.info("duplicate_file_shared_event_ignored", file_id=file_id)
            return
        _PROCESSED_FILE_IDS[file_id] = now

        try:
            info_res = await client.files_info(file=file_id)
            file_data = info_res.get("file", {})
            filename = file_data.get("name", "transcript.txt")
            file_url = file_data.get("url_private_download")

            # Determine thread_ts from shares or file timestamp
            shares = file_data.get("shares", {})
            thread_ts = ""
            for ch_type in ["public", "private"]:
                if channel_id in shares.get(ch_type, {}):
                    share_list = shares[ch_type][channel_id]
                    if share_list:
                        thread_ts = share_list[0].get("thread_ts") or share_list[0].get("ts", "")
                        break
            if not thread_ts:
                thread_ts = str(file_data.get("timestamp", ""))

            if file_url:
                await orchestrator.handle_transcript_upload(
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    user_id=user_id,
                    file_url=file_url,
                    filename=filename,
                    client=client,
                )
        except Exception as exc:
            logger.error("error_handling_file_shared", error=str(exc))

    @bolt_app.event("message")
    async def handle_message_events(event: dict[str, Any], say: Any, client: Any) -> None:
        """Handle incoming DM messages and thread replies."""
        # Ignore bot messages, message edits, and file_share events (handled by file_shared)
        if event.get("bot_id") or event.get("subtype") in [
            "message_changed",
            "bot_message",
            "file_share",
        ]:
            return

        # If message contains an @mention, let handle_app_mention handle it
        if "<@" in event.get("text", ""):
            return

        channel_id = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts", "")
        user_id = event.get("user", "")
        text = event.get("text", "").strip()

        # Check for attached files
        files = event.get("files", [])
        if files:
            for file_info in files:
                f_id = file_info.get("id")
                now = time.time()
                if (
                    f_id
                    and f_id in _PROCESSED_FILE_IDS
                    and (now - _PROCESSED_FILE_IDS[f_id]) < 60.0
                ):
                    logger.info("duplicate_file_in_message_ignored", file_id=f_id)
                    continue
                if f_id:
                    _PROCESSED_FILE_IDS[f_id] = now
                file_url = file_info.get("url_private_download")
                filename = file_info.get("name", "transcript.txt")
                if file_url:
                    await orchestrator.handle_transcript_upload(
                        channel_id=channel_id,
                        thread_ts=thread_ts,
                        user_id=user_id,
                        file_url=file_url,
                        filename=filename,
                        client=client,
                    )
            return

        # Otherwise treat as follow-up query or revision instruction
        if text:
            try:
                response = await orchestrator.handle_user_message(
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    user_id=user_id,
                    message_text=text,
                    client=client,
                )
                await say(text=response, thread_ts=thread_ts)
            except Exception as exc:
                logger.error("error_handling_message", error=str(exc))
                await say(
                    blocks=build_error_card("Error Processing Message", str(exc)),
                    thread_ts=thread_ts,
                )

    @bolt_app.action("approve_draft")
    async def handle_approve_draft(ack: Any, body: dict[str, Any], client: Any) -> None:
        """Handle user clicking 'Approve & Generate DOCX'."""
        await ack()
        channel_id = body.get("channel", {}).get("id", "")
        message = body.get("message", {})
        thread_ts = message.get("thread_ts") or message.get("ts", "")
        user_id = body.get("user", {}).get("id", "")

        actions = body.get("actions", [])
        action_val = actions[0].get("value", "") if actions else ""
        session_id_override = None
        if ":" in action_val:
            _, session_id_override = action_val.split(":", 1)

        logger.info(
            "draft_approved_by_user",
            user=user_id,
            channel=channel_id,
            thread_ts=thread_ts,
            session_id_override=session_id_override,
        )
        try:
            await orchestrator.handle_draft_approval(
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                client=client,
                session_id_override=session_id_override,
            )
        except Exception as exc:
            logger.error("approval_handling_failed", error=str(exc))
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                blocks=build_error_card("Document Generation Failed", str(exc)),
            )

    @bolt_app.action("retry_last_action")
    async def handle_retry_last_action(ack: Any, body: dict[str, Any], client: Any) -> None:
        """Handle user clicking 'Retry Operation'."""
        await ack()
        channel_id = body.get("channel", {}).get("id", "")
        message = body.get("message", {})
        thread_ts = message.get("thread_ts") or message.get("ts", "")
        user_id = body.get("user", {}).get("id", "")

        try:
            await orchestrator.handle_draft_approval(
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                client=client,
            )
        except Exception as exc:
            logger.error("retry_handling_failed", error=str(exc))
            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                blocks=build_error_card("Document Generation Failed", str(exc)),
            )

    @bolt_app.action("open_regenerate_modal")
    async def handle_open_regenerate_modal(ack: Any, body: dict[str, Any], client: Any) -> None:
        """Open the section picker modal when user clicks 'Regenerate Section'."""
        await ack()
        trigger_id = body.get("trigger_id")
        action_value = body.get("actions", [{}])[0].get("value", "1")
        if ":" in action_value:
            version_str, _ = action_value.split(":", 1)
        else:
            version_str = action_value
        draft_version = int(version_str) if version_str.isdigit() else 1

        try:
            await client.views_open(
                trigger_id=trigger_id,
                view=build_regenerate_section_modal(draft_version),
            )
        except SlackApiError as exc:
            logger.error("failed_opening_modal", error=str(exc))

    @bolt_app.view("regenerate_section_submission")
    async def handle_regenerate_submission(ack: Any, body: dict[str, Any], client: Any) -> None:
        """Handle modal submission for section regeneration."""
        await ack()
        values = body.get("view", {}).get("state", {}).get("values", {})
        selected_section = (
            values.get("section_select_block", {})
            .get("selected_section", {})
            .get("selected_option", {})
            .get("value", "")
        )
        revision_prompt = (
            values.get("revision_instructions_block", {})
            .get("revision_prompt", {})
            .get("value", "")
        )
        user_id = body.get("user", {}).get("id", "")

        logger.info(
            "section_regeneration_requested",
            section=selected_section,
            user=user_id,
            prompt=revision_prompt,
        )

        await orchestrator.handle_section_revision(
            user_id=user_id,
            section_key=selected_section,
            revision_prompt=revision_prompt,
            client=client,
        )
