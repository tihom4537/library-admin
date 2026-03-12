"""
Admin — Weekly Nudge Manager

Weekly nudges are sent to all librarians on Monday (activity suggestion)
and Thursday (motivational message). AI generates drafts each Sunday;
admins review, edit, approve, and send.

  GET    /admin/nudges                      paginated list (filter: week, status, type)
  POST   /admin/nudges                      create manual draft
  GET    /admin/nudges/{id}                 detail
  PUT    /admin/nudges/{id}                 update content / status
  POST   /admin/nudges/{id}/approve         approve a draft
  POST   /admin/nudges/{id}/send            send approved nudge to all librarians
  POST   /admin/nudges/ai-draft             generate AI draft for a week (on-demand)
"""
import logging
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin, require_role
from app.ai.gemini import generate_weekly_nudge
from app.db.database import get_db
from app.models.admin import AdminUser, WeeklyNudge
from app.models.librarian import Librarian
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nudges", tags=["admin-nudges"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class NudgeCreate(BaseModel):
    week_start_date: date
    nudge_type: str         # monday_activity | thursday_motivational
    content_kn: str
    content_en: str | None = None


class NudgeUpdate(BaseModel):
    content_kn: str | None = None
    content_en: str | None = None
    status: str | None = None   # draft | approved | sent


class AIDraftRequest(BaseModel):
    week_start_date: date
    nudge_type: str
    recent_activities: list[str] = []


class NudgeResponse(BaseModel):
    id: str
    week_start_date: date
    nudge_type: str
    content_kn: str
    content_en: str | None
    status: str
    generated_by: str
    sent_at: datetime | None
    sent_count: int
    created_at: datetime


class NudgeSendResponse(BaseModel):
    attempted: int
    succeeded: int
    failed: int


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _nudge_to_response(n: WeeklyNudge) -> NudgeResponse:
    return NudgeResponse(
        id=str(n.id),
        week_start_date=n.week_start_date,
        nudge_type=n.nudge_type,
        content_kn=n.content_kn,
        content_en=n.content_en,
        status=n.status,
        generated_by=n.generated_by,
        sent_at=n.sent_at,
        sent_count=n.sent_count,
        created_at=n.created_at,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NudgeResponse])
async def list_nudges(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    status: str = Query(""),
    nudge_type: str = Query(""),
    week: str = Query(""),   # ISO date: "2025-01-06"
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(WeeklyNudge)
    if status:
        stmt = stmt.where(WeeklyNudge.status == status)
    if nudge_type:
        stmt = stmt.where(WeeklyNudge.nudge_type == nudge_type)
    if week:
        try:
            w = date.fromisoformat(week)
            stmt = stmt.where(WeeklyNudge.week_start_date == w)
        except ValueError:
            pass
    stmt = stmt.order_by(WeeklyNudge.week_start_date.desc(), WeeklyNudge.nudge_type)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    nudges = (await db.execute(stmt)).scalars().all()
    return [_nudge_to_response(n) for n in nudges]


@router.post("", response_model=NudgeResponse, status_code=201)
async def create_nudge(
    body: NudgeCreate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    if body.nudge_type not in ("monday_activity", "thursday_motivational"):
        raise HTTPException(400, "nudge_type must be monday_activity | thursday_motivational")

    n = WeeklyNudge(
        week_start_date=body.week_start_date,
        nudge_type=body.nudge_type,
        content_kn=body.content_kn,
        content_en=body.content_en,
        status="draft",
        generated_by="manual",
        created_by_id=admin.id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    logger.info("WeeklyNudge created manually: %s by %s", n.id, admin.email)
    return _nudge_to_response(n)


@router.post("/ai-draft", response_model=NudgeResponse, status_code=201)
async def ai_draft_nudge(
    body: AIDraftRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI draft nudge on-demand and save as draft."""
    if body.nudge_type not in ("monday_activity", "thursday_motivational"):
        raise HTTPException(400, "nudge_type must be monday_activity | thursday_motivational")

    try:
        result = await generate_weekly_nudge(
            nudge_type=body.nudge_type,
            week_start_date=body.week_start_date.isoformat(),
            recent_activities=body.recent_activities,
        )
    except ValueError as e:
        raise HTTPException(502, f"AI error: {e}")

    n = WeeklyNudge(
        week_start_date=body.week_start_date,
        nudge_type=body.nudge_type,
        content_kn=result.get("content_kn", ""),
        content_en=result.get("content_en"),
        status="draft",
        generated_by="ai",
        created_by_id=admin.id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    logger.info("WeeklyNudge AI draft created: %s for week %s", n.id, body.week_start_date)
    return _nudge_to_response(n)


@router.get("/{nudge_id}", response_model=NudgeResponse)
async def get_nudge(
    nudge_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WeeklyNudge).where(WeeklyNudge.id == nudge_id))
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(404, "Nudge not found")
    return _nudge_to_response(n)


@router.put("/{nudge_id}", response_model=NudgeResponse)
async def update_nudge(
    nudge_id: UUID,
    body: NudgeUpdate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WeeklyNudge).where(WeeklyNudge.id == nudge_id))
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(404, "Nudge not found")
    if n.status == "sent":
        raise HTTPException(400, "Cannot edit a nudge that has already been sent")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(n, field, value)

    await db.commit()
    await db.refresh(n)
    return _nudge_to_response(n)


@router.post("/{nudge_id}/approve", response_model=NudgeResponse)
async def approve_nudge(
    nudge_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(WeeklyNudge).where(WeeklyNudge.id == nudge_id))
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(404, "Nudge not found")
    if n.status == "sent":
        raise HTTPException(400, "Nudge already sent")
    n.status = "approved"
    await db.commit()
    await db.refresh(n)
    logger.info("WeeklyNudge approved: %s by %s", nudge_id, admin.email)
    return _nudge_to_response(n)


@router.post("/{nudge_id}/send", response_model=NudgeSendResponse)
async def send_nudge(
    nudge_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Send an approved nudge to all onboarded librarians via Whatomate."""
    result = await db.execute(select(WeeklyNudge).where(WeeklyNudge.id == nudge_id))
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(404, "Nudge not found")
    if n.status == "sent":
        raise HTTPException(400, "Nudge already sent")
    if n.status != "approved":
        raise HTTPException(400, "Nudge must be approved before sending")

    # Get all onboarded librarians with a phone number
    libs_result = await db.execute(
        select(Librarian.phone, Librarian.name).where(
            Librarian.status == "onboarded",
            Librarian.phone.isnot(None),
        )
    )
    librarians = libs_result.all()

    attempted = len(librarians)
    succeeded = 0
    failed = 0

    for phone, name in librarians:
        try:
            await whatomate.send_text(
                contact_id=phone,  # fallback: use phone as identifier
                text=n.content_kn,
            )
            succeeded += 1
        except Exception as e:
            logger.warning("Nudge send failed for %s: %s", phone, e)
            failed += 1

    # Mark as sent
    n.status = "sent"
    n.sent_at = datetime.now(timezone.utc)
    n.sent_count = succeeded
    await db.commit()

    logger.info(
        "WeeklyNudge %s sent: %d/%d succeeded by %s",
        nudge_id, succeeded, attempted, admin.email,
    )
    return NudgeSendResponse(attempted=attempted, succeeded=succeeded, failed=failed)
