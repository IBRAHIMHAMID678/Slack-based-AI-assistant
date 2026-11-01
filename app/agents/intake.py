"""Intake Agent for extracting structured client profiles from discovery transcripts.

Enforces zero-hallucination extraction, verbatim source quote provenance,
missing field identification, and conflict/ambiguity detection.
"""

from app.agents.base import BaseAgent, wrap_untrusted
from app.llm.client import complete
from app.llm.schemas import ClientProfileExtraction
from app.rag.chunker import clean_untrusted_text


class IntakeAgent(BaseAgent):
    """Agent responsible for discovery transcript intake and fact extraction."""

    def __init__(self) -> None:
        super().__init__(name="intake_agent", prompt_template_name="intake")

    async def run(
        self,
        raw_transcript: str,
        filename: str = "transcript.txt",
        session_id: str | None = None,
    ) -> ClientProfileExtraction:
        """Extract validated ClientProfileExtraction from raw transcript."""
        cleaned = clean_untrusted_text(raw_transcript)

        # Boundary condition: Empty or trivial transcript
        if not cleaned or len(cleaned.strip()) < 20:
            self.logger.warning("empty_or_trivial_transcript_received", session_id=session_id)
            return ClientProfileExtraction(
                company_name=None,
                industry=None,
                problem=None,
                goals=[],
                budget=None,
                timeline=None,
                stakeholders=[],
                field_provenance={},
                missing_fields=[
                    "company_name",
                    "industry",
                    "problem",
                    "goals",
                    "budget",
                    "timeline",
                ],
                ambiguities=[],
            )

        delimited_transcript = wrap_untrusted(
            content=cleaned,
            doc_id=filename,
            source_type="transcript",
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Extract client discovery facts from this transcript:\n\n{delimited_transcript}",
            },
        ]

        result: ClientProfileExtraction = await complete(
            task="intake_extract",
            messages=messages,
            schema=ClientProfileExtraction,
        )
        self.logger.info(
            "intake_extraction_complete",
            company=result.company_name,
            missing_count=len(result.missing_fields),
            ambiguity_count=len(result.ambiguities),
        )
        return result
