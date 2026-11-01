"""Critic Agent enforcing anti-hallucination verification and automated repair.

Executes Appendix A checks across factual traceability, number provenance,
required section completeness, gap handling, and prompt leakage.
"""

from app.agents.base import BaseAgent, load_prompt_template, wrap_untrusted
from app.llm.client import complete
from app.llm.schemas import (
    ClientProfileExtraction,
    CriticReport,
    DraftPlanSchema,
    ResearchContextItem,
)


class CriticAgent(BaseAgent):
    """Adversarial reviewer preventing hallucinations before human review."""

    def __init__(self) -> None:
        super().__init__(name="critic_agent", prompt_template_name="critic")
        self.repair_prompt = load_prompt_template("repair")

    async def run(
        self,
        profile: ClientProfileExtraction,
        draft: DraftPlanSchema,
        raw_transcript: str,
        context_items: list[ResearchContextItem],
    ) -> CriticReport:
        """Evaluate draft sections against transcript and reference chunks."""
        sections_dump = "\n\n".join(
            f"### Section: {s.section_key} ({s.title})\n{s.content}" for s in draft.sections
        )

        delimited_transcript = wrap_untrusted(raw_transcript, "transcript", "transcript")
        delimited_profile = wrap_untrusted(profile.model_dump_json(indent=2), "profile", "profile")
        delimited_chunks = "\n\n".join(
            wrap_untrusted(
                f"[{c.proposal_id} §{c.section_heading}]: {c.text}",
                c.proposal_id,
                "proposal",
            )
            for c in context_items
        )

        user_content = (
            f"REVIEW THIS PROPOSAL DRAFT:\n\n"
            f"DRAFT SECTIONS:\n{sections_dump}\n\n"
            f"CLIENT PROFILE:\n{delimited_profile}\n\n"
            f"CLIENT TRANSCRIPT:\n{delimited_transcript}\n\n"
            f"RETRIEVED REFERENCE CHUNKS:\n{delimited_chunks}\n\n"
            f"Check strictly against the 7 evaluation criteria and return JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        report: CriticReport = await complete(
            task="critic_review",
            messages=messages,
            schema=CriticReport,
        )

        self.logger.info(
            "critic_evaluation_finished",
            passed=report.pass_verdict,
            issue_count=len(report.issues),
        )
        return report

    async def repair_draft(
        self,
        draft: DraftPlanSchema,
        critic_report: CriticReport,
        profile: ClientProfileExtraction,
        raw_transcript: str,
        context_items: list[ResearchContextItem],
    ) -> DraftPlanSchema:
        """Perform a single targeted repair pass to fix defects flagged by the Critic."""
        if critic_report.pass_verdict or not critic_report.issues:
            return draft

        self.logger.info("critic_initiating_targeted_repair", issue_count=len(critic_report.issues))
        issues_summary = "\n".join(
            f"• [{iss.issue_type}] Section '{iss.section}': '{iss.quote}' -> Fix: {iss.fix}"
            for iss in critic_report.issues
        )

        sections_dump = "\n\n".join(
            f"### Section: {s.section_key} ({s.title})\n{s.content}" for s in draft.sections
        )

        user_content = (
            f"REPAIR THIS PROPOSAL DRAFT BASED ON CRITIC DEFECTS:\n\n"
            f"CRITIC DEFECTS IDENTIFIED:\n{issues_summary}\n\n"
            f"CURRENT DRAFT SECTIONS:\n{sections_dump}\n\n"
            f"Apply the required fixes and return the complete corrected draft adhering to DraftPlanSchema."
        )

        messages = [
            {"role": "system", "content": self.repair_prompt},
            {"role": "user", "content": user_content},
        ]

        repaired_draft: DraftPlanSchema = await complete(
            task="writer_section",
            messages=messages,
            schema=DraftPlanSchema,
        )
        return repaired_draft
