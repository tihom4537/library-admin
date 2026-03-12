import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TechSupportTicket(Base):
    """
    Created when a librarian reports a tech issue that was not self-resolved.
    status: open | escalated | resolved | unknown
    """
    __tablename__ = "tech_support_ticket"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # power | internet | keyboard | shikshanapedia | other
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # open → escalated (no self-resolve) or resolved
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    # URL of escalation photo (if librarian sent one)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When follow-up was/should be sent
    followup_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    followup_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LocalContent(Base):
    """
    Local stories, songs, games, crafts submitted by librarians.
    Reviewed by admin before publishing to all libraries.
    """
    __tablename__ = "local_content"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # story | song | game | craft | other
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Raw description or transcription
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # submitted | reviewed | published | rejected
    status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
