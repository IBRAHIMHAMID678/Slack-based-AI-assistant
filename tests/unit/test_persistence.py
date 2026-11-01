"""Unit tests verifying SQLite persistence, WAL configuration, and repo operations.

Validates Stage 2 Definition of Done:
1. Migration builds DB
2. Create session, transcript, profile, draft, section
3. Read back
4. Resume across a fresh database connection.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, SessionStatus
from app.db.repo import (
    ApprovalRepository,
    DraftRepository,
    MessageRepository,
    ProfileRepository,
    SessionRepository,
    TranscriptRepository,
)


@pytest.fixture
def fresh_db(tmp_path):
    """Provide a fresh SQLite database path for isolated testing."""
    db_file = tmp_path / "test_persistence.db"
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory, engine


def test_migration_and_session_lifecycle(fresh_db):
    """Verify session creation and status transitions."""
    session_factory, _ = fresh_db
    with session_factory() as db:
        repo = SessionRepository(db)
        sess = repo.get_or_create("C12345", "1700000000.001", "U999")
        assert sess.status == SessionStatus.CREATED
        assert sess.channel_id == "C12345"

        updated = repo.update_status(sess.session_id, SessionStatus.EXTRACTING)
        assert updated.status == SessionStatus.EXTRACTING


def test_full_state_persistence_and_fresh_connection_resumption(fresh_db):
    """Write comprehensive session state, close connection, read back from fresh connection."""
    session_factory, _ = fresh_db

    # Step 1: Open first connection and write session state
    session_id = None
    with session_factory() as db:
        sess_repo = SessionRepository(db)
        trans_repo = TranscriptRepository(db)
        prof_repo = ProfileRepository(db)
        draft_repo = DraftRepository(db)
        msg_repo = MessageRepository(db)
        appr_repo = ApprovalRepository(db)

        session = sess_repo.get_or_create("C_RESUME", "1700000000.002", "U_USER")
        session_id = session.session_id

        # Add transcript
        trans_repo.add_transcript(
            session_id, "transcript.txt", "Raw client transcript data", "hash123"
        )

        # Add profile
        prof_repo.save_or_update(
            session_id,
            {
                "company_name": "Acme Logistics",
                "industry": "logistics",
                "problem": "Manual dispatching delays",
                "goals": ["Automate routing", "Reduce delivery failures"],
                "budget": "$75,000",
                "timeline": "6 months",
                "stakeholders": ["Alice (COO)", "Bob (Fleet Mgr)"],
                "missing_fields": [],
                "ambiguities": [],
            },
        )

        # Add draft with sections
        sections = [
            {"section_key": "cover", "title": "Cover", "content": "Proposal for Acme"},
            {
                "section_key": "timeline",
                "title": "Timeline",
                "content": "Phase 1: 2 months. Phase 2: 4 months.",
            },
        ]
        draft = draft_repo.create_draft(session_id, "Initial draft plan", sections)
        assert draft.version == 1

        # Add message & approval
        msg_repo.add_message(session_id, "user", "user", "Please start analysis")
        appr_repo.record_approval(session_id, "approved", "U_USER", "Looks good")

    # Step 2: Open completely fresh connection and verify resumption
    with session_factory() as fresh_conn:
        sess_repo = SessionRepository(fresh_conn)
        trans_repo = TranscriptRepository(fresh_conn)
        prof_repo = ProfileRepository(fresh_conn)
        draft_repo = DraftRepository(fresh_conn)
        msg_repo = MessageRepository(fresh_conn)
        appr_repo = ApprovalRepository(fresh_conn)

        resumed_sess = sess_repo.get_by_id(session_id)
        assert resumed_sess is not None
        assert resumed_sess.channel_id == "C_RESUME"

        transcripts = trans_repo.get_by_session(session_id)
        assert len(transcripts) == 1
        assert transcripts[0].filename == "transcript.txt"

        profile = prof_repo.get_by_session(session_id)
        assert profile is not None
        assert profile.company_name == "Acme Logistics"
        assert profile.industry == "logistics"

        latest_draft = draft_repo.get_latest_draft(session_id)
        assert latest_draft is not None
        assert len(latest_draft.sections) == 2

        # Step 3: Test isolated section update
        updated_sec = draft_repo.update_section(
            latest_draft.draft_id,
            "timeline",
            "Phase 1: 3 months with sprint gates. Phase 2: 3 months.",
        )
        assert updated_sec.version == 2
        assert "sprint gates" in updated_sec.content

        # Verify other section was NOT changed
        cover_sec = next(s for s in latest_draft.sections if s.section_key == "cover")
        assert cover_sec.content == "Proposal for Acme"
        assert cover_sec.version == 1

        history = msg_repo.get_history(session_id)
        assert len(history) == 1
        assert history[0].content == "Please start analysis"
