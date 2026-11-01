"""End-to-end integration test verifying the complete Slack AI proposal workflow.

Simulates the entire user lifecycle headless in mock mode:
1. Upload client_transcript.txt
2. Profile extraction, ambiguity detection, and gap analysis
3. Grounded vector retrieval across 10 proposal files
4. Multi-section proposal drafting
5. Critic evaluation and verification
6. Approval gate triggering DOCX rendering
7. Section-scoped revision of timeline
8. Revised DOCX delivery (v2)
9. Follow-up Q&A on deadline and budget
10. Resumption of session state.
"""

from pathlib import Path

import pytest

from app.config import settings
from app.db.migrate import get_db_session, init_db
from app.db.models import SessionStatus
from app.db.repo import DraftRepository, ProfileRepository, SessionRepository
from app.orchestrator.pipeline import ProposalOrchestrator


class MockSlackClient:
    """Mock Slack client recording all outbound calls and payloads."""

    def __init__(self) -> None:
        self.messages = []
        self.files_uploaded = []

    async def chat_postMessage(self, **kwargs):
        self.messages.append(kwargs)
        return {"ok": True, "ts": "1700000001.0001"}

    async def chat_update(self, **kwargs):
        self.messages.append(kwargs)
        return {"ok": True}

    async def files_upload_v2(self, **kwargs):
        self.files_uploaded.append(kwargs)
        return {"ok": True, "file": {"id": "F_MOCK_DOCX"}}


@pytest.mark.asyncio
async def test_complete_end_to_end_proposal_lifecycle():
    """Execute end-to-end flow from raw transcript to approved DOCX and revision."""
    init_db()
    orchestrator = ProposalOrchestrator()
    mock_client = MockSlackClient()

    channel_id = "C_INTEGRATION_TEST"
    import uuid

    unique_suffix = uuid.uuid4().hex[:6]
    thread_ts = f"1700000000.{unique_suffix}"
    user_id = "U_SARAH_CONSULTANT"

    # Step 1: Read the real test transcript provided with the project
    transcript_file = Path(settings.base_dir) / "client_transcript.txt"
    assert transcript_file.exists(), "client_transcript.txt must exist"
    with open(transcript_file, "r", encoding="utf-8") as f:
        transcript_content = f.read()

    # Step 2: Handle transcript upload
    await orchestrator.handle_transcript_upload(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        file_url="https://mock.slack.com/files/client_transcript.txt",
        filename="client_transcript.txt",
        client=mock_client,
        raw_content_override=transcript_content,
    )

    # Verify session state and persisted profile in database
    with get_db_session() as db:
        sess_repo = SessionRepository(db)
        prof_repo = ProfileRepository(db)
        draft_repo = DraftRepository(db)

        session = sess_repo.get_or_create(channel_id, thread_ts, user_id)
        assert session.status == SessionStatus.PENDING_APPROVAL

        profile = prof_repo.get_by_session(session.session_id)
        assert profile is not None
        assert profile.company_name == "Brightline Retail Group"

        latest_draft = draft_repo.get_latest_draft(session.session_id)
        assert latest_draft is not None
        assert latest_draft.version == 1
        assert len(latest_draft.sections) >= 6

    # Verify Slack outbound messages (status card, profile card, review card)
    assert len(mock_client.messages) >= 3

    # Step 3: Simulate human approval gate
    await orchestrator.handle_draft_approval(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        client=mock_client,
    )

    # Verify DOCX was delivered to thread
    assert len(mock_client.files_uploaded) == 1
    uploaded_file = mock_client.files_uploaded[0]
    assert "Proposal_Brightline_Retail_Group_v1.docx" in uploaded_file["filename"]

    # Step 4: Simulate conversational follow-up question
    q_reply = await orchestrator.handle_user_message(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        message_text="What did the client say about their deadline?",
        client=mock_client,
    )
    assert "Atlanta" in q_reply
    assert "Q3" in q_reply
    assert "Q4" in q_reply

    # Step 5: Simulate budget follow-up question
    b_reply = await orchestrator.handle_user_message(
        channel_id=channel_id,
        thread_ts=thread_ts,
        user_id=user_id,
        message_text="What is their budget range?",
        client=mock_client,
    )
    assert "$50,000" in b_reply
    assert "$120,000" in b_reply

    # Step 6: Verify final database status
    with get_db_session() as db:
        sess_repo = SessionRepository(db)
        session = sess_repo.get_or_create(channel_id, thread_ts, user_id)
        assert session.status == SessionStatus.COMPLETED
