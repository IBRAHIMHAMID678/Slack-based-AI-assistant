"""SQLAlchemy 2.0 database models for state persistence.

All session state, client profiles, draft versions, section revisions,
conversation history, and approval gates are persisted to SQLite.
"""

import enum
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy entities."""


class SessionStatus(str, enum.Enum):
    """Lifecycle status states for an interactive proposal session."""

    CREATED = "CREATED"
    INGESTING = "INGESTING"
    EXTRACTING = "EXTRACTING"
    RESEARCHING = "RESEARCHING"
    DRAFTING = "DRAFTING"
    CRITIQUING = "CRITIQUING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Session(Base):
    """Root conversation session keyed by Slack coordinates."""

    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("channel_id", "thread_ts", "user_id", name="uq_session_coordinates"),
    )

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    thread_ts: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), default=SessionStatus.CREATED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    transcripts: Mapped[list["Transcript"]] = relationship("Transcript", back_populates="session")
    profile: Mapped[Optional["ClientProfile"]] = relationship(
        "ClientProfile", back_populates="session", uselist=False
    )
    drafts: Mapped[list["Draft"]] = relationship("Draft", back_populates="session")
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="session")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="session")


class Transcript(Base):
    """Uploaded client discovery transcripts associated with a session."""

    __tablename__ = "transcripts"

    transcript_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["Session"] = relationship("Session", back_populates="transcripts")


class ClientProfile(Base):
    """Structured extraction output from the Intake Agent."""

    __tablename__ = "client_profiles"

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), unique=True, nullable=False
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    goals_json: Mapped[str] = mapped_column(Text, default="[]")
    budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stakeholders_json: Mapped[str] = mapped_column(Text, default="[]")
    missing_fields_json: Mapped[str] = mapped_column(Text, default="[]")
    ambiguities_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["Session"] = relationship("Session", back_populates="profile")


class Draft(Base):
    """A generated proposal draft version."""

    __tablename__ = "drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    plan_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    session: Mapped["Session"] = relationship("Session", back_populates="drafts")
    sections: Mapped[list["DraftSection"]] = relationship(
        "DraftSection", back_populates="draft", order_by="DraftSection.section_order"
    )


class DraftSection(Base):
    """An individual section within a proposal draft version."""

    __tablename__ = "draft_sections"

    section_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.draft_id"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    draft: Mapped["Draft"] = relationship("Draft", back_populates="sections")


class Message(Base):
    """Conversational history and user queries within a session thread."""

    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    sender: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["Session"] = relationship("Session", back_populates="messages")


class Approval(Base):
    """Reviewer approval state and gate feedback."""

    __tablename__ = "approvals"

    approval_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    session: Mapped["Session"] = relationship("Session", back_populates="approvals")
