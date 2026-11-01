"""Pydantic V2 schemas enforcing strict validation on agent inputs and outputs.

Implements structured extraction, citation provenance, draft plans,
critic evaluations, and revision requests.
"""

from pydantic import BaseModel, ConfigDict, Field


class ClientFieldItem(BaseModel):
    """Encapsulates a field value with its supporting verbatim quote and confidence."""

    model_config = ConfigDict(extra="ignore")
    value: str | None = None
    source_quote: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AmbiguityItem(BaseModel):
    """Captures contradictory or ambiguous statements from a transcript."""

    model_config = ConfigDict(extra="ignore")
    field: str
    quote: str
    reason: str


class ClientProfileExtraction(BaseModel):
    """Structured extraction model output from Intake Agent."""

    model_config = ConfigDict(extra="ignore")
    company_name: str | None = None
    industry: str | None = None
    problem: str | None = None
    goals: list[str] = Field(default_factory=list)
    budget: str | None = None
    timeline: str | None = None
    stakeholders: list[str] = Field(default_factory=list)
    field_provenance: dict[str, ClientFieldItem] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    ambiguities: list[AmbiguityItem] = Field(default_factory=list)


class ResearchContextItem(BaseModel):
    """Retrieved reference proposal chunk with provenance score."""

    model_config = ConfigDict(extra="ignore")
    proposal_id: str
    section_heading: str
    score: float
    text: str
    citation: str


class DraftSectionSchema(BaseModel):
    """Structured section within a proposal draft."""

    model_config = ConfigDict(extra="ignore")
    section_key: str
    title: str
    content: str
    citations: list[str] = Field(default_factory=list)


class DraftPlanSchema(BaseModel):
    """Complete multi-section proposal plan produced by Writer Agent."""

    model_config = ConfigDict(extra="ignore")
    plan_reasoning: str
    sections: list[DraftSectionSchema]


class CriticIssue(BaseModel):
    """Defect or hallucination identified by Critic Agent."""

    model_config = ConfigDict(extra="ignore")
    section: str
    issue_type: str
    quote: str
    fix: str


class CriticReport(BaseModel):
    """Output from Critic Agent following Appendix A rubric."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    pass_verdict: bool = Field(alias="pass")
    issues: list[CriticIssue] = Field(default_factory=list)
