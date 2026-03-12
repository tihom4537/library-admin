import uuid
from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ActivityTemplate(Base):
    """
    Library activity templates (e.g., Reading Stars, Art Competition).
    Seeded from department circulars or created by admin.
    """
    __tablename__ = "activity_template"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title_kn: Mapped[str] = mapped_column(String(300), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    # reading | art | science | craft | story | digital | outdoor
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # all | 5-8 | 8-12 | 12+
    age_group: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # easy | medium | hard
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_children: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_children: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Structured steps: [{order, text_kn, text_en, image_url}]
    # Kept instructions_kn for backward compat with existing bot code
    instructions_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps_kn: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    materials_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    # S3 object keys for reference images (up to 5)
    reference_image_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Type: regular | digital | outdoor
    type: Mapped[str] = mapped_column(String(20), default="regular", nullable=False)
    # Status: draft | published | archived  (replaces approved bool going forward)
    approved: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="published", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduledActivity(Base):
    """
    Activities scheduled by department admins for specific dates/targets.
    Mandatory activities (⭐) are shown first with deadline.
    """
    __tablename__ = "scheduled_activity"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Optional link to the circular this came from
    circular_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Scope: all | district | taluk
    target_scope: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    # e.g. {"districts": ["Belagavi", "Dharwad"]}
    target_filter: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Optional circular reference number for traceability
    circular_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Notification tracking
    immediate_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActivityReport(Base):
    """
    Submitted by librarians after conducting an activity.
    Created from WhatsApp Flow (activity_report_flow) response.
    """
    __tablename__ = "activity_report"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    scheduled_activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    activity_template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    activity_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    conducted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # lt10 | ten_twenty | twenty_thirty | gt30
    approximate_children_count: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo_urls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    voice_note_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # went_well | needs_improvement | difficult
    librarian_feedback: Mapped[str | None] = mapped_column(String(30), nullable=True)
    optional_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # flow | voice | text
    reported_via: Mapped[str] = mapped_column(String(20), default="flow", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MicroLearningModule(Base):
    """
    Weekly micro-learning content sent to librarians via WhatsApp Flow.
    """
    __tablename__ = "micro_learning_module"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title_kn: Mapped[str] = mapped_column(String(300), nullable=False)
    step_one_heading_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_one_text_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_one_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_two_heading_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_two_text_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_two_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_three_heading_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_three_text_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_three_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    practice_prompt_kn: Mapped[str | None] = mapped_column(Text, nullable=True)
    # computer | library | reading | craft
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LibrarianLearningProgress(Base):
    """Tracks each librarian's progress through micro-learning modules."""
    __tablename__ = "librarian_learning_progress"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    librarian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    practice_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    practice_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # done | problem
    librarian_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
