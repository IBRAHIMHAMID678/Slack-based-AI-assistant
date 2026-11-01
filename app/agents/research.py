"""Research Agent for semantic vector retrieval and context structuring.

Executes query synthesis and queries the Chroma knowledge base via the
retrieval fallback ladder.
"""

from typing import Any

from app.agents.base import BaseAgent
from app.llm.schemas import ClientProfileExtraction, ResearchContextItem
from app.rag.retrieve import retrieve_proposal_context


class ResearchAgent(BaseAgent):
    """Agent responsible for grounding proposals with past engagement context."""

    def __init__(self) -> None:
        super().__init__(name="research_agent", prompt_template_name="research")

    async def run(
        self,
        profile: ClientProfileExtraction,
        top_k: int = 4,
    ) -> dict[str, Any]:
        """Synthesize retrieval query and execute fallback ladder against Chroma."""
        # Formulate query from profile requirements
        query_parts: list[str] = []
        if profile.industry:
            query_parts.append(profile.industry)
        if profile.problem:
            query_parts.append(profile.problem[:150])
        if profile.goals:
            query_parts.append(" ".join(profile.goals[:2]))

        query_str = " ".join(query_parts) if query_parts else "business operations proposal"
        self.logger.info(
            "research_agent_executing_retrieval",
            query=query_str,
            industry=profile.industry,
        )

        retrieval_res = retrieve_proposal_context(
            query=query_str,
            industry=profile.industry,
            top_k=top_k,
        )

        context_items: list[ResearchContextItem] = []
        for c in retrieval_res.chunks:
            meta = c.get("metadata", {})
            proposal_id = meta.get("source_id", "proposal_reference")
            heading = meta.get("heading_path", "Overview")
            score = c.get("score", 0.0)
            text = c.get("document", "")
            citation = f"[{proposal_id} §{heading}]"

            context_items.append(
                ResearchContextItem(
                    proposal_id=proposal_id,
                    section_heading=heading,
                    score=score,
                    text=text,
                    citation=citation,
                )
            )

        return {
            "context_items": context_items,
            "low_confidence": retrieval_res.low_confidence,
            "ladder_step": retrieval_res.ladder_step,
        }
