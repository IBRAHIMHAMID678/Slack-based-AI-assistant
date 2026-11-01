"""Modal dialog definitions for Slack interactive workflows.

Provides Block Kit view payloads for section-scoped regeneration
and user feedback collection.
"""

from typing import Any


def build_regenerate_section_modal(draft_version: int) -> dict[str, Any]:
    """Return Block Kit view for selecting a single section to regenerate."""
    return {
        "type": "modal",
        "callback_id": "regenerate_section_submission",
        "private_metadata": str(draft_version),
        "title": {
            "type": "plain_text",
            "text": "Regenerate Section",
            "emoji": True,
        },
        "submit": {
            "type": "plain_text",
            "text": "Regenerate",
            "emoji": True,
        },
        "close": {
            "type": "plain_text",
            "text": "Cancel",
            "emoji": True,
        },
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Select the section you want to revise. Only this section will be "
                        "regenerated; the rest of the proposal will remain untouched."
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "section_select_block",
                "element": {
                    "type": "static_select",
                    "action_id": "selected_section",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose a section...",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Cover Section"},
                            "value": "cover",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Executive Summary"},
                            "value": "executive_summary",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Proposed Solution"},
                            "value": "proposed_solution",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Timeline"},
                            "value": "timeline",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Budget Range"},
                            "value": "budget_range",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Next Steps"},
                            "value": "next_steps",
                        },
                    ],
                },
                "label": {
                    "type": "plain_text",
                    "text": "Target Section",
                },
            },
            {
                "type": "input",
                "block_id": "revision_instructions_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "revision_prompt",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "e.g., Detail the Q3 launch milestones and specify the fallback to Q4.",
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": "Revision Instructions",
                },
            },
        ],
    }
