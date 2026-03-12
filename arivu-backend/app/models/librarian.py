import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Librarian(Base):
    __tablename__ = "librarian"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    library_name: Mapped[str] = mapped_column(String(200), nullable=False)
    library_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    taluk: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gram_panchayat: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Status: pending | onboarded | inactive
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Language preference (default: kn for Kannada)
    language_pref: Mapped[str] = mapped_column(String(5), default="kn", nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Whatomate's contact UUID for this librarian (needed to send messages via Whatomate API)
    whatomate_contact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Librarian {self.name} ({self.phone})>"


class ConversationSession(Base):
    """
    Redis-backed session with Postgres as durable fallback.
    Redis key: session:{phone} → {state, context, librarian_id}
    """
    __tablename__ = "conversation_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Current state in the state machine
    # States: IDLE | ONBOARDING | MAIN | FLOW_1 | FLOW_2 | FLOW_3 | FLOW_4 | FLOW_5 | FLOW_6
    state: Mapped[str] = mapped_column(String(50), default="IDLE", nullable=False)
    # Arbitrary context for the current flow (e.g., which activity being viewed)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # incoming | outgoing
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    # text | image | audio | nfm_reply | button_reply | template | flow
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Intent classified by Sarvam AI (for incoming text messages)
    intent_classified: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # The bot's response content (for logging)
    bot_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Redis session ID at time of message
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
