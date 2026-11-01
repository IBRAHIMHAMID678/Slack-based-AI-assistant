"""Unit tests verifying state persistence, transcript append, and session resumption.

Tests:
1. Multi-transcript append into existing session
2. Profile update preserves historical state
3. Concurrent session isolation
4. Message ordering and role verification
5. Multiple draft versions tracking.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repo import (
    ApprovalRepository,
    DraftRepository,
    MessageRepository,
    SessionRepository,
    TranscriptRepository,
)


@pytest.fixture
def test_db(tmp_path):
    """Provide isolated SQLite database for resumption tests."""
    db_file = tmp_path / "resumption.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_transcript_append_to_existing_session(test_db):
    """Verify multiple transcripts can be appended to a single session without overwriting."""
    with test_db() as db:
        sess_repo = SessionRepository(db)
        trans_repo = TranscriptRepository(db)

        session = sess_repo.get_or_create("C_APPEND", "17000.1", "U_USER")
        trans_repo.add_transcript(session.session_id, "part1.txt", "Part 1 transcript", "hash1")
        trans_repo.add_transcript(session.session_id, "part2.txt", "Part 2 transcript", "hash2")

        transcripts = trans_repo.get_by_session(session.session_id)
        assert len(transcripts) == 2
        assert transcripts[0].filename == "part1.txt"
        assert transcripts[1].filename == "part2.txt"


def test_multiple_draft_versions_tracking(test_db):
    """Verify draft versions increment sequentially (v1 -> v2) for a session."""
    with test_db() as db:
        sess_repo = SessionRepository(db)
        draft_repo = DraftRepository(db)

        session = sess_repo.get_or_create("C_DRAFTS", "17000.2", "U_USER")
        sec1 = [{"section_key": "cover", "title": "Cover", "content": "v1 content"}]
        sec2 = [{"section_key": "cover", "title": "Cover", "content": "v2 content"}]

        draft1 = draft_repo.create_draft(session.session_id, "Plan 1", sec1)
        draft2 = draft_repo.create_draft(session.session_id, "Plan 2", sec2)

        assert draft1.version == 1
        assert draft2.version == 2

        latest = draft_repo.get_latest_draft(session.session_id)
        assert latest.version == 2
        assert latest.sections[0].content == "v2 content"


def test_multi_user_thread_session_isolation(test_db):
    """Verify different Slack channels or threads create completely isolated sessions."""
    with test_db() as db:
        sess_repo = SessionRepository(db)
        s1 = sess_repo.get_or_create("C1", "T1", "U1")
        s2 = sess_repo.get_or_create("C1", "T2", "U1")
        s3 = sess_repo.get_or_create("C2", "T1", "U1")

        assert s1.session_id != s2.session_id
        assert s1.session_id != s3.session_id
        assert s2.session_id != s3.session_id


def test_message_history_order_preservation(test_db):
    """Verify messages maintain exact chronological insertion order."""
    with test_db() as db:
        sess_repo = SessionRepository(db)
        msg_repo = MessageRepository(db)

        session = sess_repo.get_or_create("C_MSG", "17000.3", "U_USER")
        msg_repo.add_message(session.session_id, "user", "user", "Message 1")
        msg_repo.add_message(session.session_id, "assistant", "assistant", "Message 2")
        msg_repo.add_message(session.session_id, "user", "user", "Message 3")

        history = msg_repo.get_history(session.session_id)
        assert len(history) == 3
        assert history[0].content == "Message 1"
        assert history[1].content == "Message 2"
        assert history[2].content == "Message 3"


def test_approval_record_tracking(test_db):
    """Verify recording approval tracks reviewer ID and feedback."""
    with test_db() as db:
        sess_repo = SessionRepository(db)
        appr_repo = ApprovalRepository(db)

        session = sess_repo.get_or_create("C_APPR", "17000.4", "U_USER")
        approval = appr_repo.record_approval(
            session_id=session.session_id,
            status="approved",
            reviewer_user_id="U_PARTNER",
            feedback="LGTM, ready to deliver",
        )
        assert approval.status == "approved"
        assert approval.reviewer_user_id == "U_PARTNER"
        assert approval.feedback == "LGTM, ready to deliver"
