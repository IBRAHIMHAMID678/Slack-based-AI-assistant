"""Repository layer abstracting all database operations.

Enforces zero SQL outside the db/ module and provides atomic transactions
for sessions, transcripts, client profiles, draft sections, and approvals.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.db.models import (
    Approval,
    ClientProfile,
    Draft,
    DraftSection,
    Message,
    Session,
    SessionStatus,
    Transcript,
)
from app.errors import SessionNotFoundError


class SessionRepository:
    """Repository handling Session persistence and lifecycle state transitions."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def get_or_create(self, channel_id: str, thread_ts: str, user_id: str) -> Session:
        """Fetch existing session by Slack coordinates or create a new one."""
        stmt = select(Session).where(
            Session.channel_id == channel_id,
            Session.thread_ts == thread_ts,
            Session.user_id == user_id,
        )
        session = self.db.execute(stmt).scalar_one_or_none()
        if not session:
            session = Session(
                session_id=str(uuid.uuid4()),
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                status=SessionStatus.CREATED,
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    def get_by_id(self, session_id: str) -> Session | None:
        """Retrieve session by primary key."""
        stmt = select(Session).where(Session.session_id == session_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def update_status(self, session_id: str, status: SessionStatus) -> Session:
        """Update the lifecycle status of a session."""
        session = self.get_by_id(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        session.status = status
        session.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(session)
        return session


class TranscriptRepository:
    """Repository for managing uploaded transcripts."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def add_transcript(
        self, session_id: str, filename: str, raw_content: str, sha256_hash: str
    ) -> Transcript:
        """Add a newly uploaded transcript to a session."""
        transcript = Transcript(
            transcript_id=str(uuid.uuid4()),
            session_id=session_id,
            filename=filename,
            sha256_hash=sha256_hash,
            raw_content=raw_content,
        )
        self.db.add(transcript)
        self.db.commit()
        self.db.refresh(transcript)
        return transcript

    def get_by_session(self, session_id: str) -> list[Transcript]:
        """Fetch all transcripts attached to a session."""
        stmt = select(Transcript).where(Transcript.session_id == session_id)
        return list(self.db.execute(stmt).scalars().all())


class ProfileRepository:
    """Repository for managing extracted client profiles."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def save_or_update(self, session_id: str, data: dict[str, Any]) -> ClientProfile:
        """Save new client profile or update existing one for a session."""
        stmt = select(ClientProfile).where(ClientProfile.session_id == session_id)
        profile = self.db.execute(stmt).scalar_one_or_none()
        if not profile:
            profile = ClientProfile(profile_id=str(uuid.uuid4()), session_id=session_id)
            self.db.add(profile)

        profile.company_name = data.get("company_name")
        profile.industry = data.get("industry")
        profile.problem = data.get("problem")
        profile.goals_json = json.dumps(data.get("goals", []))
        profile.budget = data.get("budget")
        profile.timeline = data.get("timeline")
        profile.stakeholders_json = json.dumps(data.get("stakeholders", []))
        profile.missing_fields_json = json.dumps(data.get("missing_fields", []))
        profile.ambiguities_json = json.dumps(data.get("ambiguities", []))

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_by_session(self, session_id: str) -> ClientProfile | None:
        """Retrieve client profile for a session."""
        stmt = select(ClientProfile).where(ClientProfile.session_id == session_id)
        return self.db.execute(stmt).scalar_one_or_none()


class DraftRepository:
    """Repository for managing proposal drafts and section versions."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def create_draft(
        self, session_id: str, plan_log: str, sections_data: list[dict[str, Any]]
    ) -> Draft:
        """Create a new proposal draft with initial sections."""
        stmt = select(Draft).where(Draft.session_id == session_id).order_by(Draft.version.desc())
        latest = self.db.execute(stmt).scalars().first()
        next_version = (latest.version + 1) if latest else 1

        draft = Draft(
            draft_id=str(uuid.uuid4()),
            session_id=session_id,
            version=next_version,
            status="drafted",
            plan_log=plan_log,
        )
        self.db.add(draft)
        self.db.flush()

        for idx, sec in enumerate(sections_data):
            draft_section = DraftSection(
                section_id=str(uuid.uuid4()),
                draft_id=draft.draft_id,
                section_key=sec["section_key"],
                title=sec["title"],
                content=sec["content"],
                section_order=idx + 1,
                version=1,
                citations_json=json.dumps(sec.get("citations", [])),
            )
            self.db.add(draft_section)

        self.db.commit()
        self.db.refresh(draft)
        return draft

    def get_latest_draft(self, session_id: str) -> Draft | None:
        """Fetch the latest draft version for a session with sections loaded."""
        stmt = select(Draft).where(Draft.session_id == session_id).order_by(Draft.version.desc())
        return self.db.execute(stmt).scalars().first()

    def update_section(
        self,
        draft_id: str,
        section_key: str,
        new_content: str,
        citations: list[str] | None = None,
    ) -> DraftSection:
        """Update a specific section within a draft without modifying others."""
        stmt = select(DraftSection).where(
            DraftSection.draft_id == draft_id,
            DraftSection.section_key == section_key,
        )
        sec = self.db.execute(stmt).scalar_one_or_none()
        if not sec:
            raise ValueError(f"Draft section '{section_key}' not found in draft '{draft_id}'")

        sec.content = new_content
        sec.version += 1
        if citations is not None:
            sec.citations_json = json.dumps(citations)
        sec.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(sec)
        return sec


class MessageRepository:
    """Repository for persisting conversation history."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def add_message(self, session_id: str, sender: str, role: str, content: str) -> Message:
        """Record an incoming or outgoing message in the session thread."""
        msg = Message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            sender=sender,
            role=role,
            content=content,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_history(self, session_id: str) -> list[Message]:
        """Fetch chronological message history for a session."""
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
        return list(self.db.execute(stmt).scalars().all())


class ApprovalRepository:
    """Repository for tracking human-in-the-loop approvals."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def record_approval(
        self,
        session_id: str,
        status: str,
        reviewer_user_id: str,
        feedback: str | None = None,
    ) -> Approval:
        """Record an approval or rejection event."""
        approval = Approval(
            approval_id=str(uuid.uuid4()),
            session_id=session_id,
            status=status,
            reviewer_user_id=reviewer_user_id,
            feedback=feedback,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval
