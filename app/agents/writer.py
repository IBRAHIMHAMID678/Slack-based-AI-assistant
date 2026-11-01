"""Writer Agent for structured proposal generation and section-scoped revisions.

Synthesizes client profiles and retrieved context into multi-section proposals
with strict provenance citations and gap placeholders.
"""

from app.agents.base import BaseAgent, wrap_untrusted
from app.llm.client import complete
from app.llm.schemas import (
    ClientProfileExtraction,
    DraftPlanSchema,
    DraftSectionSchema,
    ResearchContextItem,
)


class WriterAgent(BaseAgent):
    """Agent responsible for drafting proposals and revising individual sections."""

    def __init__(self) -> None:
        super().__init__(name="writer_agent", prompt_template_name="writer")

    async def run(
        self,
        profile: ClientProfileExtraction,
        context_items: list[ResearchContextItem],
    ) -> DraftPlanSchema:
        """Draft complete multi-section proposal plan based on profile and chunks."""
        # Delimit retrieved reference context
        context_blocks = "\n\n".join(
            wrap_untrusted(
                content=f"Heading: {item.section_heading}\n{item.text}",
                doc_id=item.proposal_id,
                source_type="proposal",
            )
            for item in context_items
        )

        profile_json = profile.model_dump_json(indent=2)
        delimited_profile = wrap_untrusted(
            content=profile_json,
            doc_id="extracted_client_profile",
            source_type="profile",
        )

        user_content = (
            f"Draft a tailored multi-section proposal using the client profile and reference context:\n\n"
            f"CLIENT PROFILE:\n{delimited_profile}\n\n"
            f"RETRIEVED REFERENCE CHUNKS:\n{context_blocks}\n\n"
            f"Ensure all 6 required sections are present with strict numerical provenance."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        result: DraftPlanSchema = await complete(
            task="writer_section",
            messages=messages,
            schema=DraftPlanSchema,
        )
        self.logger.info("proposal_drafting_complete", section_count=len(result.sections))
        return result

    async def revise_section(
        self,
        section_key: str,
        current_content: str,
        revision_instructions: str,
        profile: ClientProfileExtraction,
        context_items: list[ResearchContextItem],
    ) -> DraftSectionSchema:
        """Revise a single targeted section while preserving existing surrounding prose."""
        profile_json = profile.model_dump_json(indent=2)
        delimited_profile = wrap_untrusted(profile_json, "client_profile", "profile")
        delimited_current = wrap_untrusted(current_content, f"section_{section_key}", "section")

        user_content = (
            f"Revise ONLY the section '{section_key}'.\n\n"
            f"USER REVISION INSTRUCTIONS:\n{revision_instructions}\n\n"
            f"CURRENT SECTION CONTENT:\n{delimited_current}\n\n"
            f"CLIENT PROFILE:\n{delimited_profile}\n\n"
            f"Maintain strict numerical provenance and consultant voice."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Use writer task with section-specific return
        result_plan: DraftPlanSchema = await complete(
            task="writer_section",
            messages=messages,
            schema=DraftPlanSchema,
        )

        # Match section or use first returned section
        for s in result_plan.sections:
            if s.section_key == section_key:
                return s
        if result_plan.sections:
            target = result_plan.sections[0]
            target.section_key = section_key
            return target

        return DraftSectionSchema(
            section_key=section_key,
            title=section_key.replace("_", " ").title(),
            content=current_content,
        )
