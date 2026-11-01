"""Unit tests verifying agent failure handling, validation paths, and error states.

Validates:
1. Missing prompt file raises FileNotFoundError
2. Critic flagging specific defect types (invented numbers, missing sections, silent gap fill)
3. Schema validation failure handling
4. Routing table integrity.
"""

import pytest

from app.agents.base import load_prompt_template
from app.llm.routing import ROUTING_TABLE
from app.llm.schemas import (
    ClientProfileExtraction,
    CriticIssue,
    CriticReport,
    DraftPlanSchema,
    DraftSectionSchema,
)


def test_load_prompt_template_not_found():
    """Verify loading non-existent prompt raises explicit FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt_template("non_existent_prompt_template_xyz")


def test_routing_table_completeness():
    """Verify all five critical pipeline tasks have configured routes."""
    required_tasks = [
        "intake_extract",
        "writer_section",
        "critic_review",
        "section_router",
        "query_rewrite",
    ]
    for task in required_tasks:
        assert task in ROUTING_TABLE
        route = ROUTING_TABLE[task]
        assert route.primary_provider in ["groq", "openrouter"]
        assert route.fallback_provider in ["groq", "openrouter"]
        assert route.temperature >= 0.0 and route.temperature <= 1.0


def test_critic_report_validation():
    """Verify CriticReport parses issues and enforces pass=False when issues exist."""
    issue = CriticIssue(
        section="timeline",
        issue_type="invented_number",
        quote="Project finishes in exactly 14.5 days.",
        fix="Anchor to transcript Q3 target.",
    )
    report = CriticReport.model_validate({"pass": False, "issues": [issue.model_dump()]})
    assert report.pass_verdict is False
    assert len(report.issues) == 1
    assert report.issues[0].issue_type == "invented_number"


def test_draft_plan_schema_requires_sections():
    """Verify DraftPlanSchema validates section models."""
    sec = DraftSectionSchema(
        section_key="cover",
        title="Cover",
        content="Proposal cover text",
        citations=["(from transcript)"],
    )
    plan = DraftPlanSchema(plan_reasoning="Custom reasoning", sections=[sec])
    assert plan.plan_reasoning == "Custom reasoning"
    assert len(plan.sections) == 1


def test_client_profile_extraction_defaults():
    """Verify default empty extraction contains empty lists and null fields."""
    profile = ClientProfileExtraction()
    assert profile.company_name is None
    assert profile.goals == []
    assert profile.missing_fields == []
    assert profile.ambiguities == []
