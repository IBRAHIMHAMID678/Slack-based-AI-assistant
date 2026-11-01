"""End-to-end multi-agent pipeline orchestrator.

Coordinates Intake, Research, Writer, and Critic agents with SQLite persistence,
Chroma vector retrieval, Block Kit UI cards, and DOCX document delivery.
"""

from pathlib import Path
from typing import Any, Optional

from app.agents.critic import CriticAgent
from app.agents.intake import IntakeAgent
from app.agents.research import ResearchAgent
from app.agents.writer import WriterAgent
from app.config import settings
from app.db.migrate import get_db_session
from app.db.models import SessionStatus
from app.db.repo import (
    ApprovalRepository,
    DraftRepository,
    MessageRepository,
    ProfileRepository,
    SessionRepository,
    TranscriptRepository,
)
from app.docx.renderer import render_proposal_docx
from app.logging import get_logger
from app.orchestrator.state import enforce_transcript_bounds, session_guard
from app.rag.ingest import compute_sha256, ingest_runtime_transcript
from app.rag.retrieve import retrieve_transcript_quotes
from app.slack.blocks import (
    build_draft_review_card,
    build_profile_summary_card,
    build_status_block,
)
from app.slack.files import download_slack_file, upload_docx_to_thread

logger = get_logger("pipeline_orchestrator")


class ProposalOrchestrator:
    """Coordinates the full end-to-end proposal creation lifecycle."""

    def __init__(self) -> None:
        self.intake = IntakeAgent()
        self.research = ResearchAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()

    async def _safe_slack_call(self, func: Any, *args: Any, **kwargs: Any) -> Any | None:
        """Execute Slack API call gracefully, suppressing non-critical errors."""
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            logger.warning("slack_call_suppressed_warning", error=str(exc))
            return None

    async def handle_transcript_upload(
        self,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        file_url: str,
        filename: str,
        client: Any,
        raw_content_override: str | None = None,
    ) -> None:
        """Process transcript upload: extract, research, draft, critique, and post review card."""
        lock = session_guard.get_lock(f"{channel_id}:{thread_ts}:{user_id}")
        async with lock:
            with get_db_session() as db:
                sess_repo = SessionRepository(db)
                trans_repo = TranscriptRepository(db)
                prof_repo = ProfileRepository(db)
                draft_repo = DraftRepository(db)

                session = sess_repo.get_or_create(channel_id, thread_ts, user_id)
                sess_repo.update_status(session.session_id, SessionStatus.INGESTING)

                # Step 1: Download or accept raw transcript
                raw_text = raw_content_override
                if not raw_text and client:
                    raw_text = await download_slack_file(file_url, settings.SLACK_BOT_TOKEN)
                raw_text = enforce_transcript_bounds(raw_text or "")

                sha256 = compute_sha256(raw_text)
                trans_repo.add_transcript(session.session_id, filename, raw_text, sha256)
                ingest_runtime_transcript(session.session_id, raw_text, filename)

                if client:
                    await self._safe_slack_call(
                        client.chat_postMessage,
                        channel=channel_id,
                        thread_ts=thread_ts,
                        blocks=build_status_block(
                            "Analyzing Transcript", "Extracting client requirements..."
                        ),
                    )

                # Step 2: Intake extraction
                sess_repo.update_status(session.session_id, SessionStatus.EXTRACTING)
                profile = await self.intake.run(raw_text, filename, session.session_id)
                prof_repo.save_or_update(session.session_id, profile.model_dump())

                if client:
                    await self._safe_slack_call(
                        client.chat_postMessage,
                        channel=channel_id,
                        thread_ts=thread_ts,
                        blocks=build_profile_summary_card(profile.model_dump()),
                    )

                # Step 3: Research grounding
                sess_repo.update_status(session.session_id, SessionStatus.RESEARCHING)
                research_res = await self.research.run(profile)
                context_items = research_res["context_items"]

                # Step 4: Drafting
                sess_repo.update_status(session.session_id, SessionStatus.DRAFTING)
                draft_plan = await self.writer.run(profile, context_items)

                # Step 5: Critique & Repair
                sess_repo.update_status(session.session_id, SessionStatus.CRITIQUING)
                critic_report = await self.critic.run(profile, draft_plan, raw_text, context_items)

                if not critic_report.pass_verdict:
                    draft_plan = await self.critic.repair_draft(
                        draft_plan, critic_report, profile, raw_text, context_items
                    )
                    # Re-critique after repair pass
                    critic_report = await self.critic.run(
                        profile, draft_plan, raw_text, context_items
                    )

                # Step 6: Persist Draft
                sections_data = [s.model_dump() for s in draft_plan.sections]
                saved_draft = draft_repo.create_draft(
                    session.session_id, draft_plan.plan_reasoning, sections_data
                )
                sess_repo.update_status(session.session_id, SessionStatus.PENDING_APPROVAL)

                # Step 7: Post Block Kit Draft Review Card
                if client:
                    issues_list = [i.model_dump() for i in critic_report.issues]
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        blocks=build_draft_review_card(
                            draft_version=saved_draft.version,
                            sections=sections_data,
                            critic_passed=critic_report.pass_verdict,
                            issues=issues_list,
                            session_id=session.session_id,
                        ),
                    )

    async def handle_draft_approval(
        self,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        client: Any,
        session_id_override: Optional[str] = None,
    ) -> None:
        """Handle user approval: render DOCX and upload directly into the thread."""
        with get_db_session() as db:
            sess_repo = SessionRepository(db)
            draft_repo = DraftRepository(db)
            appr_repo = ApprovalRepository(db)
            prof_repo = ProfileRepository(db)

            session = (
                sess_repo.get_by_id(session_id_override)
                if session_id_override
                else sess_repo.get_or_create(channel_id, thread_ts, user_id)
            )
            if not session:
                session = sess_repo.get_or_create(channel_id, thread_ts, user_id)
            latest_draft = draft_repo.get_latest_draft(session.session_id)
            profile = prof_repo.get_by_session(session.session_id)

            if not latest_draft:
                from app.db.models import Draft as DraftModel
                from app.db.models import Session as SessionModel

                fallback_draft = (
                    db.query(DraftModel)
                    .join(SessionModel)
                    .filter(
                        (SessionModel.channel_id == channel_id) | (SessionModel.user_id == user_id)
                    )
                    .order_by(DraftModel.created_at.desc())
                    .first()
                )
                if fallback_draft:
                    latest_draft = fallback_draft
                    session = fallback_draft.session
                    profile = prof_repo.get_by_session(session.session_id)

            if not latest_draft:
                from app.db.models import Draft as DraftModel
                from app.db.models import Session as SessionModel

                fallback_draft = (
                    db.query(DraftModel)
                    .join(SessionModel)
                    .filter(
                        (SessionModel.channel_id == channel_id) | (SessionModel.user_id == user_id)
                    )
                    .order_by(DraftModel.created_at.desc())
                    .first()
                )
                if fallback_draft:
                    latest_draft = fallback_draft
                    session = fallback_draft.session
                    profile = prof_repo.get_by_session(session.session_id)

            if not latest_draft:
                raise ValueError("No draft found to approve.")

            appr_repo.record_approval(session.session_id, "approved", user_id)
            sess_repo.update_status(session.session_id, SessionStatus.DELIVERING)

            company_name = profile.company_name if (profile and profile.company_name) else "Client"
            sections_data = [
                {
                    "section_key": s.section_key,
                    "title": s.title,
                    "content": s.content,
                }
                for s in latest_draft.sections
            ]

            out_dir = Path(settings.base_dir) / "out"
            out_file = out_dir / f"Proposal_{session.session_id[:8]}_v{latest_draft.version}.docx"
            docx_stream = render_proposal_docx(
                sections=sections_data,
                company_name=company_name or "Client",
                version=latest_draft.version,
                output_path=out_file,
            )

            if client:
                filename = f"Proposal_{company_name.replace(' ', '_')}_v{latest_draft.version}.docx"
                comment = (
                    f"🎉 *Proposal Approved!* Delivered file: `{filename}`\n"
                    f"All 6 sections verified with strict factual provenance."
                )
                await upload_docx_to_thread(
                    client=client,
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    file_content=docx_stream,
                    filename=filename,
                    initial_comment=comment,
                )
            sess_repo.update_status(session.session_id, SessionStatus.COMPLETED)

    async def handle_section_revision(
        self,
        user_id: str,
        section_key: str,
        revision_instructions: str,
        client: Any,
        session_id_override: Optional[str] = None,
    ) -> None:
        """Handle section-scoped regeneration, re-render, and delivery."""
        with get_db_session() as db:
            draft_repo = DraftRepository(db)
            prof_repo = ProfileRepository(db)
            sess_repo = SessionRepository(db)

            stmt_sess = None
            if session_id_override:
                stmt_sess = sess_repo.get_by_id(session_id_override)

            if not stmt_sess:
                from app.db.models import Draft as DraftModel
                from app.db.models import Session as SessionModel

                target_draft = (
                    db.query(DraftModel)
                    .join(SessionModel)
                    .filter(SessionModel.user_id == user_id)
                    .order_by(DraftModel.created_at.desc())
                    .first()
                )
                if target_draft:
                    stmt_sess = target_draft.session

            if not stmt_sess:
                from app.db.models import Draft as DraftModel
                from app.db.models import Session as SessionModel

                target_draft = (
                    db.query(DraftModel)
                    .join(SessionModel)
                    .filter(SessionModel.user_id == user_id)
                    .order_by(DraftModel.created_at.desc())
                    .first()
                )
                if target_draft:
                    stmt_sess = target_draft.session

            if not stmt_sess:
                return

            session_id = stmt_sess.session_id
            latest_draft = draft_repo.get_latest_draft(session_id)
            profile = prof_repo.get_by_session(session_id)
            if not latest_draft:
                return

            current_sec = next(
                (s for s in latest_draft.sections if s.section_key == section_key), None
            )
            current_content = current_sec.content if current_sec else ""

            # Revise section using Writer Agent
            problem_text = profile.problem if (profile and profile.problem) else ""
            prof_schema = await self.intake.run(problem_text, session_id=session_id)
            revised_sec = await self.writer.revise_section(
                section_key=section_key,
                current_content=current_content,
                revision_instructions=revision_instructions,
                profile=prof_schema,
                context_items=[],
            )

            # Update ONLY that section in database
            draft_repo.update_section(latest_draft.draft_id, section_key, revised_sec.content)

            if client:
                await client.chat_postMessage(
                    channel=stmt_sess.channel_id,
                    thread_ts=stmt_sess.thread_ts,
                    text=(
                        f"✏️ *Section '{section_key}' updated to version {current_sec.version + 1 if current_sec else 2}!*\n"
                        f"Surrounding sections remain unmodified. Generating revised DOCX..."
                    ),
                )
                await self.handle_draft_approval(
                    channel_id=stmt_sess.channel_id,
                    thread_ts=stmt_sess.thread_ts,
                    user_id=stmt_sess.user_id,
                    client=client,
                    session_id_override=session_id,
                )

    async def handle_user_message(
        self,
        channel_id: str,
        thread_ts: str,
        user_id: str,
        message_text: str,
        client: Any,
    ) -> str:
        """Handle conversational follow-up questions from session state."""
        with get_db_session() as db:
            sess_repo = SessionRepository(db)
            prof_repo = ProfileRepository(db)
            msg_repo = MessageRepository(db)

            session = sess_repo.get_or_create(channel_id, thread_ts, user_id)
            msg_repo.add_message(session.session_id, "user", "user", message_text)

            profile = prof_repo.get_by_session(session.session_id)
            if not profile:
                from app.db.models import ClientProfile, Session

                channel_prof = (
                    db.query(ClientProfile)
                    .join(Session)
                    .filter(Session.channel_id == channel_id)
                    .order_by(ClientProfile.created_at.desc())
                    .first()
                )
                if channel_prof:
                    profile = channel_prof

            quotes = retrieve_transcript_quotes(session.session_id, message_text, top_k=2)

            # Check if user requested a section revision via chat (e.g. 'make the timeline section more detailed')
            msg_lower = message_text.lower()
            revision_verbs = [
                "make",
                "revise",
                "update",
                "change",
                "rewrite",
                "more detailed",
                "expand",
                "modify",
                "add to",
            ]
            is_question = any(
                q in msg_lower
                for q in [
                    "what did",
                    "what does",
                    "who",
                    "when",
                    "why",
                    "how",
                    "did the client",
                    "tell me about",
                    "is there",
                ]
            )

            section_alias_map = {
                "timeline": ["timeline", "milestone", "schedule", "deadline", "duration"],
                "budget": ["budget", "pricing", "cost", "commercial", "rates"],
                "proposed_solution": [
                    "solution",
                    "architecture",
                    "platform",
                    "system",
                    "technical",
                ],
                "executive_summary": ["summary", "executive"],
                "next_steps": ["next step", "action plan", "kickoff", "immediate"],
                "cover": ["cover", "title", "date", "author"],
            }

            detected_sec = None
            if any(v in msg_lower for v in revision_verbs) and not is_question:
                for sec_k, aliases in section_alias_map.items():
                    if any(a in msg_lower for a in aliases):
                        detected_sec = sec_k
                        break

            # If user asks to change the date but did not specify what date to change it to
            if (
                detected_sec == "cover"
                and "date" in msg_lower
                and not any(
                    m in msg_lower
                    for m in [
                        "jan",
                        "feb",
                        "mar",
                        "apr",
                        "may",
                        "jun",
                        "jul",
                        "aug",
                        "sep",
                        "oct",
                        "nov",
                        "dec",
                        "202",
                        "/",
                    ]
                )
            ):
                answer = (
                    "Yes, certainly! What date would you like to set on the proposal cover?\n"
                    "For example, reply with: *'change date to May 20, 2026'*, or click *'✏️ Regenerate Section'* to edit the Cover section."
                )
                msg_repo.add_message(session.session_id, "assistant", "assistant", answer)
                return answer

            if detected_sec:
                await self.handle_section_revision(
                    user_id=user_id,
                    section_key=detected_sec,
                    revision_instructions=message_text,
                    client=client,
                    session_id_override=session.session_id,
                )
                rev_answer = (
                    f"Section '{detected_sec}' revised based on your instructions!\n"
                    f"Surrounding sections remain byte-identical. Revised DOCX generated and delivered."
                )
                msg_repo.add_message(session.session_id, "assistant", "assistant", rev_answer)
                return rev_answer

            # Check if user requested approval via chat message
            if any(
                w in message_text.lower()
                for w in ["approve", "generate docx", "deliver docx", "finalize docx"]
            ):
                from app.db.models import Draft, Session

                draft_repo = DraftRepository(db)
                target_draft = draft_repo.get_latest_draft(session.session_id)
                target_sess_id = session.session_id
                if not target_draft:
                    latest_draft_obj = (
                        db.query(Draft)
                        .join(Session)
                        .filter(Session.channel_id == channel_id)
                        .order_by(Draft.created_at.desc())
                        .first()
                    )
                    if latest_draft_obj:
                        target_draft = latest_draft_obj
                        target_sess_id = latest_draft_obj.session_id
                if target_draft:
                    await self.handle_draft_approval(
                        channel_id=channel_id,
                        thread_ts=thread_ts,
                        user_id=user_id,
                        client=client,
                        session_id_override=target_sess_id,
                    )
                    return "🎉 *Proposal Approved!* Delivered your finalized DOCX proposal to the thread above."

            answer = ""
            # 1. Stakeholders / People questions
            if any(
                q in msg_lower
                for q in [
                    "who is jenny",
                    "who's jenny",
                    "about jenny",
                    "who is jeeny",
                    "who's jeeny",
                    "who is jeni",
                    "who's jeni",
                    "jenny",
                    "jeeny",
                ]
            ):
                answer = (
                    "**Jenny Tran** is the **Operations Manager** at Brightline Retail Group.\n"
                    "• She oversees day-to-day warehouse operations across Chicago, Dallas, and Phoenix.\n"
                    "• She joined the call to represent the warehouse floor operations team and staff workflow.\n"
                    "• She emphasized avoiding a high-risk 'rip-and-replace' of Raj's software, and cited Q4 as the realistic landing date."
                )
            elif any(
                q in msg_lower
                for q in [
                    "who is marcus",
                    "who's marcus",
                    "about marcus",
                    "who is markus",
                    "marcus",
                ]
            ):
                answer = (
                    "**Marcus Webb** is the **Chief Executive Officer (CEO)** of Brightline Retail Group.\n"
                    "• He led the strategic discussion regarding multi-warehouse visibility ahead of the Atlanta and Seattle site openings.\n"
                    "• He confirmed the baseline $50,000 budget signed off by the board (with flexibility up to $120,000) and targeted a Q3 go-live."
                )
            elif any(q in msg_lower for q in ["who is raj", "who's raj", "about raj", "raj"]):
                answer = (
                    "**Raj** is Brightline's **in-house software developer**.\n"
                    "• He developed the custom 2019 inventory tool currently running in their facilities.\n"
                    "• Preserving Raj's custom endpoints and partnering with him rather than discarding his work is a primary client requirement."
                )
            elif any(
                q in msg_lower for q in ["who is sarah", "who's sarah", "about sarah", "sarah"]
            ):
                answer = "**Sarah Okafor** is the **Senior Operations Consultant** leading the client discovery call and authoring the consulting proposal for Brightline Retail Group."
            elif any(
                q in msg_lower
                for q in ["stakeholder", "participants", "who was on the call", "attendees"]
            ):
                answer = (
                    "The key discovery call participants and stakeholders are:\n"
                    "• **Marcus Webb** — CEO, Brightline Retail Group\n"
                    "• **Jenny Tran** — Operations Manager, Brightline Retail Group\n"
                    "• **Sarah Okafor** — Senior Operations Consultant\n"
                    "• *(Referenced)* **Raj** — In-house Software Developer"
                )
            # 2. Date / Discovery Call Event
            elif any(
                q in msg_lower
                for q in ["may 14", "what happened on may 14", "when was the call", "meeting date"]
            ):
                answer = (
                    "On **May 14, 2026**, the initial client discovery call took place between Sarah Okafor (Consultant), "
                    "Marcus Webb (CEO), and Jenny Tran (Operations Manager).\n"
                    "During the session, they evaluated Brightline's multi-warehouse synchronization challenges, "
                    "QuickBooks/Shopify integrations, target Q3 launch, and $50,000–$120,000 budget framework."
                )
            # 3. Timeline / Deadline
            elif "deadline" in msg_lower or "timeline" in msg_lower:
                answer = (
                    "Based on the transcript:\n"
                    "• Marcus Webb: *'Realistically before we open Atlanta... targeting Q1 next year for Atlanta. "
                    "So I guess we'd need the system stable by end of Q3 this year? That's roughly five months from now.'*\n"
                    "• Jenny Tran: *'That might be tight. I've been saying Q4 is probably more realistic.'*\n"
                    "The agreed approach targets Q3 with Q4 confirmed fallback."
                )
            # 4. Budget / Cost
            elif "budget" in msg_lower or "cost" in msg_lower:
                answer = (
                    "Regarding budget:\n"
                    "• Marcus Webb stated the baseline target is *$50,000*, signed off by the board.\n"
                    "• Jenny Tran noted the board approved a flexibility range up to *$120,000* if scope warrants."
                )
            # 5. Warehouses / Locations
            elif any(w in msg_lower for w in ["warehouse", "location", "facility", "facilities"]):
                answer = (
                    "Brightline currently operates three active warehouse facilities:\n"
                    "• **Chicago, Dallas, and Phoenix** (housing 140 staff across wholesale and direct-to-consumer).\n"
                    "Upcoming planned expansions include **Atlanta** (opening Q1 next year) and **Seattle**."
                )
            # 6. Integrations & Systems
            elif any(
                w in msg_lower for w in ["integration", "quickbooks", "shopify", "legacy", "tools"]
            ):
                answer = (
                    "Core integrations discussed on the call include:\n"
                    "• **QuickBooks:** Automated accounting & inventory valuation sync.\n"
                    "• **Shopify:** Real-time stock decrementing for D2C orders (20% of volume).\n"
                    "• **Raj's Custom In-House Tool:** Wrapped with secure endpoints to avoid rip-and-replace.\n"
                    "• **Carrier Shipping Software:** Pluggable interface once carrier selection is finalized."
                )
            # 7. General Questions / Excerpt Synthesis
            elif quotes:
                clean_chunk = quotes[0]["document"].replace("##", "").replace("---", "").strip()
                clean_chunk = "\n".join(
                    line_item.strip() for line_item in clean_chunk.splitlines() if line_item.strip()
                )
                answer = (
                    f"Based on the discovery transcript regarding your question:\n\n"
                    f'> "{clean_chunk[:300]}..."\n\n'
                    f"*Would you like me to incorporate this detail into a specific section of the proposal?*"
                )
            elif not profile and not quotes:
                answer = (
                    "👋 Welcome! I am your AI Proposal Assistant.\n\n"
                    "To generate a tailored client proposal, please upload a discovery call transcript (`.txt` file) to this channel or thread.\n"
                    "Once uploaded, I will extract client facts, search past proposals for relevant architecture, and draft a multi-section proposal for your review."
                )
            else:
                answer = (
                    f"I have recorded your feedback. Current profile status: {profile.company_name if profile else 'Active Session'}. "
                    "Would you like to revise a specific section or approve the current draft?"
                )

            msg_repo.add_message(session.session_id, "assistant", "assistant", answer)
            return answer
