"""
Admin — Librarian Directory

GET  /admin/librarians            paginated list with search + filters
GET  /admin/librarians/{id}       full detail: reports, learning progress
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin, require_role
from app.db.database import get_db
from app.models.activity import ActivityReport, LibrarianLearningProgress, MicroLearningModule
from app.models.admin import AdminUser
from app.models.librarian import Librarian
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/librarians", tags=["admin-librarians"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LibrarianListItem(BaseModel):
    id: str
    name: str
    phone: str
    library_name: str
    library_id: str | None
    district: str | None
    taluk: str | None
    gram_panchayat: str | None
    status: str
    last_active_at: datetime | None
    onboarded_at: datetime | None
    # Derived counts
    reports_this_month: int
    activity_status: str  # active (7d) | inactive (30d) | never_onboarded


class LibrarianListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LibrarianListItem]


class ActivityReportSummary(BaseModel):
    id: str
    activity_title: str | None
    conducted_date: str | None
    approximate_children_count: str | None
    librarian_feedback: str | None
    reported_via: str
    created_at: datetime


class LearningProgressItem(BaseModel):
    module_id: str
    module_title: str
    sent_at: datetime | None
    practice_completed: bool
    librarian_outcome: str | None


class LibrarianDetailResponse(BaseModel):
    id: str
    name: str
    phone: str
    library_name: str
    library_id: str | None
    district: str | None
    taluk: str | None
    gram_panchayat: str | None
    status: str
    language_pref: str
    last_active_at: datetime | None
    onboarded_at: datetime | None
    whatomate_contact_id: str | None
    reports_this_month: int
    total_reports: int
    recent_reports: list[ActivityReportSummary]
    learning_progress: list[LearningProgressItem]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _activity_status(librarian: Librarian) -> str:
    if librarian.status != "onboarded":
        return "never_onboarded"
    if librarian.last_active_at is None:
        return "never_onboarded"
    cutoff_active = datetime.now(timezone.utc) - timedelta(days=7)
    if librarian.last_active_at >= cutoff_active:
        return "active"
    return "inactive"


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=LibrarianListResponse)
async def list_librarians(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search name, phone, or library name"),
    district: str = Query("", description="Filter by district"),
    taluk: str = Query("", description="Filter by taluk"),
    status: str = Query("", description="pending | onboarded | inactive"),
):
    allowed_districts = district_filter(admin)

    # ── Base query ────────────────────────────────────────────────────────────
    stmt = select(Librarian)

    if allowed_districts is not None:
        stmt = stmt.where(Librarian.district.in_(allowed_districts))

    if search:
        pattern = f"%{search}%"
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Librarian.name.ilike(pattern),
                Librarian.phone.ilike(pattern),
                Librarian.library_name.ilike(pattern),
            )
        )

    if district:
        stmt = stmt.where(Librarian.district == district)
    if taluk:
        stmt = stmt.where(Librarian.taluk == taluk)
    if status:
        stmt = stmt.where(Librarian.status == status)

    # ── Total count ───────────────────────────────────────────────────────────
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # ── Paginate ──────────────────────────────────────────────────────────────
    stmt = stmt.order_by(Librarian.last_active_at.desc().nullslast())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    librarians = (await db.execute(stmt)).scalars().all()

    # ── Reports this month count (batch) ──────────────────────────────────────
    lib_ids = [lib.id for lib in librarians]
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    reports_stmt = (
        select(ActivityReport.librarian_id, func.count().label("cnt"))
        .where(
            ActivityReport.librarian_id.in_(lib_ids),
            ActivityReport.created_at >= month_start,
        )
        .group_by(ActivityReport.librarian_id)
    )
    reports_rows = (await db.execute(reports_stmt)).all()
    reports_map = {str(row.librarian_id): row.cnt for row in reports_rows}

    items = [
        LibrarianListItem(
            id=str(lib.id),
            name=lib.name,
            phone=lib.phone,
            library_name=lib.library_name,
            library_id=lib.library_id,
            district=lib.district,
            taluk=lib.taluk,
            gram_panchayat=lib.gram_panchayat,
            status=lib.status,
            last_active_at=lib.last_active_at,
            onboarded_at=lib.onboarded_at,
            reports_this_month=reports_map.get(str(lib.id), 0),
            activity_status=_activity_status(lib),
        )
        for lib in librarians
    ]

    return LibrarianListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/{librarian_id}", response_model=LibrarianDetailResponse)
async def get_librarian_detail(
    librarian_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException

    result = await db.execute(select(Librarian).where(Librarian.id == librarian_id))
    lib = result.scalar_one_or_none()
    if lib is None:
        raise HTTPException(status_code=404, detail="Librarian not found")

    # District coordinator access check
    allowed = district_filter(admin)
    if allowed is not None and lib.district not in allowed:
        raise HTTPException(status_code=403, detail="Access to this district is not permitted")

    # ── Recent activity reports (last 10) ─────────────────────────────────────
    reports_result = await db.execute(
        select(ActivityReport)
        .where(ActivityReport.librarian_id == librarian_id)
        .order_by(ActivityReport.created_at.desc())
        .limit(10)
    )
    reports = reports_result.scalars().all()

    # ── Total reports count ───────────────────────────────────────────────────
    total_count_result = await db.execute(
        select(func.count()).where(ActivityReport.librarian_id == librarian_id)
    )
    total_reports = total_count_result.scalar() or 0

    # ── Reports this month ────────────────────────────────────────────────────
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_count_result = await db.execute(
        select(func.count()).where(
            ActivityReport.librarian_id == librarian_id,
            ActivityReport.created_at >= month_start,
        )
    )
    reports_this_month = month_count_result.scalar() or 0

    # ── Learning progress ─────────────────────────────────────────────────────
    progress_result = await db.execute(
        select(LibrarianLearningProgress, MicroLearningModule.title_kn)
        .join(MicroLearningModule, LibrarianLearningProgress.module_id == MicroLearningModule.id)
        .where(LibrarianLearningProgress.librarian_id == librarian_id)
        .order_by(MicroLearningModule.sequence_order)
    )
    progress_rows = progress_result.all()

    return LibrarianDetailResponse(
        id=str(lib.id),
        name=lib.name,
        phone=lib.phone,
        library_name=lib.library_name,
        library_id=lib.library_id,
        district=lib.district,
        taluk=lib.taluk,
        gram_panchayat=lib.gram_panchayat,
        status=lib.status,
        language_pref=lib.language_pref,
        last_active_at=lib.last_active_at,
        onboarded_at=lib.onboarded_at,
        whatomate_contact_id=lib.whatomate_contact_id,
        reports_this_month=reports_this_month,
        total_reports=total_reports,
        recent_reports=[
            ActivityReportSummary(
                id=str(r.id),
                activity_title=r.activity_title,
                conducted_date=str(r.conducted_date) if r.conducted_date else None,
                approximate_children_count=r.approximate_children_count,
                librarian_feedback=r.librarian_feedback,
                reported_via=r.reported_via,
                created_at=r.created_at,
            )
            for r in reports
        ],
        learning_progress=[
            LearningProgressItem(
                module_id=str(p.module_id),
                module_title=title,
                sent_at=p.sent_at,
                practice_completed=p.practice_completed,
                librarian_outcome=p.librarian_outcome,
            )
            for p, title in progress_rows
        ],
    )


# ─── Nudge route ──────────────────────────────────────────────────────────────

class NudgeRequest(BaseModel):
    librarian_ids: list[str] = []
    send_to_all_inactive: bool = False
    template_name: str = "librarian_nudge"
    # Optional text params passed to the template
    template_params: dict = {}


class NudgeResponse(BaseModel):
    attempted: int
    succeeded: int
    failed: int
    errors: list[str]


@router.post("/nudge", response_model=NudgeResponse)
async def send_nudge(
    body: NudgeRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk send a WhatsApp template message to librarians via Whatomate API.

    Two modes:
    1. Explicit list: pass `librarian_ids`
    2. All inactive: set `send_to_all_inactive=true` — fetches from Redis inactive cache.

    Uses Whatomate send_template() which requires:
    - Librarian.whatomate_contact_id to be set (set during onboarding)
    - An approved WhatsApp template (default: librarian_nudge)
    """
    import json
    import redis.asyncio as aioredis
    from app.config import settings
    from app.scheduler.jobs import INACTIVE_KEY

    target_ids: list[str] = list(body.librarian_ids)

    if body.send_to_all_inactive:
        redis_client = await aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        try:
            raw = await redis_client.get(INACTIVE_KEY)
        finally:
            await redis_client.aclose()

        if raw:
            inactive = json.loads(raw)
            # Merge with any explicit IDs (deduplicate)
            id_set = set(target_ids)
            for item in inactive:
                id_set.add(item["id"])
            target_ids = list(id_set)

    if not target_ids:
        return NudgeResponse(attempted=0, succeeded=0, failed=0, errors=[])

    # Fetch librarians with their Whatomate contact IDs
    result = await db.execute(
        select(Librarian.id, Librarian.phone, Librarian.whatomate_contact_id, Librarian.name)
        .where(Librarian.id.in_([UUID(i) for i in target_ids]))
        .where(Librarian.status == "onboarded")
    )
    librarians = result.all()

    succeeded = 0
    failed = 0
    errors: list[str] = []

    for lib in librarians:
        try:
            if lib.whatomate_contact_id:
                await whatomate.send_template(
                    phone_number=lib.phone,
                    template_name=body.template_name,
                    params=body.template_params,
                )
            else:
                # No Whatomate contact — skip but count as failed
                errors.append(f"{lib.name} ({lib.phone}): no whatomate_contact_id")
                failed += 1
                continue
            succeeded += 1
        except Exception as e:
            errors.append(f"{lib.name} ({lib.phone}): {str(e)}")
            failed += 1
            logger.warning("Nudge failed for %s: %s", lib.phone, e)

    logger.info(
        "Nudge batch complete: attempted=%d succeeded=%d failed=%d by=%s",
        len(librarians), succeeded, failed, admin.email,
    )
    return NudgeResponse(
        attempted=len(librarians),
        succeeded=succeeded,
        failed=failed,
        errors=errors,
    )
