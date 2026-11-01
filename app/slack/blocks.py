"""Slack Block Kit builder functions for interactive, scannable UI cards.

All UI components use native Block Kit payloads with rich formatting,
threaded progress updates, and action buttons.
"""

from typing import Any


def build_welcome_card() -> list[dict[str, Any]]:
    """Build initial greeting card for bot discovery and instructions."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📋 AI Proposal Assistant",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Welcome! I transform raw client discovery call transcripts into "
                    "tailored, multi-section proposal documents with full factual provenance.\n\n"
                    "*Getting Started:*\n"
                    "• *Upload a `.txt` transcript* to this channel or DM\n"
                    "• I will extract client facts, search past proposals, and draft a proposal\n"
                    "• You review and approve before final DOCX delivery"
                ),
            },
        },
        {"type": "divider"},
    ]


def build_status_block(
    step_title: str, message: str, status_icon: str = "⏳"
) -> list[dict[str, Any]]:
    """Build a transient status update card for long-running workflows."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{status_icon} {step_title}*\n{message}",
            },
        }
    ]


def build_profile_summary_card(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Build structured summary card displaying extracted client discovery facts."""
    goals_text = "\n".join(f"• {g}" for g in profile.get("goals", [])) or "• None specified"
    missing = profile.get("missing_fields", [])
    missing_text = ", ".join(missing) if missing else "None"
    ambiguities = profile.get("ambiguities", [])
    ambiguity_text = (
        "\n".join(
            f"• *{a.get('field')}*: {a.get('reason')} (`{a.get('quote')}`)" for a in ambiguities
        )
        if ambiguities
        else "None detected"
    )

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🎯 Extracted Client Profile",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Company:*\n{profile.get('company_name', 'NOT_STATED')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Industry:*\n{profile.get('industry', 'NOT_STATED')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Target Budget:*\n{profile.get('budget', 'NOT_STATED')}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Target Timeline:*\n{profile.get('timeline', 'NOT_STATED')}",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Core Problem:*\n{profile.get('problem', 'NOT_STATED')}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Goals:*\n{goals_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*⚠️ Missing Information:*\n{missing_text}\n\n*🔍 Ambiguities Detected:*\n{ambiguity_text}",
            },
        },
    ]
    return blocks


def build_draft_review_card(
    draft_version: int,
    sections: list[dict[str, Any]],
    critic_passed: bool,
    issues: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build the human approval gate card with interactive Block Kit action buttons."""
    status_emoji = "✅ Passed All Verifications" if critic_passed else "⚠️ Flagged Review Items"
    section_bullets = "\n".join(
        f"• *{s.get('title', 'Section')}* ({len(s.get('content', ''))} chars)" for s in sections
    )
    btn_val = f"{draft_version}:{session_id}" if session_id else str(draft_version)

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📄 Proposal Draft v{draft_version} Ready for Review",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Critic Validation:* {status_emoji}\n\n*Included Sections:*\n{section_bullets}",
            },
        },
    ]

    if issues:
        issue_bullets = "\n".join(
            f"• [{iss.get('issue_type')}] *{iss.get('section')}*: {iss.get('fix')}"
            for iss in issues[:3]
        )
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Critic Observations:*\n{issue_bullets}",
                },
            }
        )

    blocks.extend(
        [
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "draft_approval_actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve & Generate DOCX",
                            "emoji": True,
                        },
                        "style": "primary",
                        "action_id": "approve_draft",
                        "value": btn_val,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✏️ Regenerate Section",
                            "emoji": True,
                        },
                        "action_id": "open_regenerate_modal",
                        "value": btn_val,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "💬 Request General Changes",
                            "emoji": True,
                        },
                        "action_id": "request_changes_prompt",
                        "value": btn_val,
                    },
                ],
            },
        ]
    )
    return blocks


def build_error_card(
    error_title: str, error_message: str, can_retry: bool = True
) -> list[dict[str, Any]]:
    """Build a user-friendly error card with optional retry action."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *{error_title}*\n{error_message}",
            },
        }
    ]
    if can_retry:
        blocks.append(
            {
                "type": "actions",
                "block_id": "error_actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔄 Retry Operation",
                            "emoji": True,
                        },
                        "style": "danger",
                        "action_id": "retry_last_action",
                        "value": "retry",
                    }
                ],
            }
        )
    return blocks
