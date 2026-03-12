"""
Admin — Activity Manager

Activity Templates (CRUD):
  GET    /admin/activities/templates           paginated list
  POST   /admin/activities/templates           create
  GET    /admin/activities/templates/{id}      detail
  PUT    /admin/activities/templates/{id}      update
  DELETE /admin/activities/templates/{id}      archive (soft delete)

Scheduling (Mandatory Activities):
  GET    /admin/activities/scheduled           list all scheduled
  POST   /admin/activities/scheduled           schedule a mandatory activity
  GET    /admin/activities/scheduled/{id}      detail
  DELETE /admin/activities/scheduled/{id}      cancel

Compliance:
  GET    /admin/activities/compliance/{scheduled_id}    % reported per district
"""
import logging
from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin, require_role
from app.ai.gemini import suggest_activity as gemini_suggest_activity
from app.ai.gemini import suggest_activities_for_occasion
from app.db.database import get_db
from app.models.activity import ActivityReport, ActivityTemplate, ScheduledActivity
from app.models.admin import AdminUser, Circular, CircularActionItem, SpecialDay
from app.models.librarian import Librarian

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activities", tags=["admin-activities"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StepSchema(BaseModel):
    order: int
    text_kn: str
    text_en: str | None = None
    image_url: str | None = None  # S3 object key


class ActivityTemplateCreate(BaseModel):
    title_kn: str
    title_en: str | None = None
    description_kn: str | None = None
    category: str | None = None       # reading | art | science | craft | story | digital | outdoor
    age_group: str | None = None      # all | 5-8 | 8-12 | 12+
    difficulty: str | None = None     # easy | medium | hard
    duration_minutes: int | None = None
    min_children: int | None = None
    max_children: int | None = None
    steps_kn: list[StepSchema] = []
    materials_kn: str | None = None
    reference_image_urls: list[str] = []
    type: str = "regular"             # regular | digital | outdoor
    status: str = "published"         # draft | published | archived


class ActivityTemplateUpdate(BaseModel):
    title_kn: str | None = None
    title_en: str | None = None
    description_kn: str | None = None
    category: str | None = None
    age_group: str | None = None
    difficulty: str | None = None
    duration_minutes: int | None = None
    min_children: int | None = None
    max_children: int | None = None
    steps_kn: list[StepSchema] | None = None
    materials_kn: str | None = None
    reference_image_urls: list[str] | None = None
    type: str | None = None
    status: str | None = None


class ActivityTemplateResponse(BaseModel):
    id: str
    title_kn: str
    title_en: str | None
    description_kn: str | None
    category: str | None
    age_group: str | None
    difficulty: str | None
    duration_minutes: int | None
    min_children: int | None
    max_children: int | None
    steps_kn: list[dict]
    materials_kn: str | None
    reference_image_urls: list[str]
    type: str
    status: str
    times_used: int
    created_at: datetime
    updated_at: datetime


class ActivityTemplateListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ActivityTemplateResponse]


class ScheduleActivityRequest(BaseModel):
    activity_template_id: UUID
    scheduled_date: date | None = None
    deadline_date: date | None = None
    target_scope: str = "all"           # all | district | taluk
    # For district/taluk scope: {"districts": ["Belagavi"]} or {"taluks": ["Hubli"]}
    target_filter: dict | None = None
    circular_reference: str | None = None
    notify_immediately: bool = True
    notify_3_days_before: bool = True
    notify_on_deadline: bool = True


class ScheduledActivityResponse(BaseModel):
    id: str
    activity_template_id: str
    activity_title: str
    scheduled_date: date | None
    deadline_date: date | None
    is_mandatory: bool
    target_scope: str
    target_filter: dict | None
    circular_reference: str | None
    immediate_sent: bool
    notification_sent: bool
    reminder_sent: bool
    created_at: datetime


class ComplianceByDistrict(BaseModel):
    district: str
    total_librarians: int
    reported_count: int
    compliance_pct: float


class ComplianceResponse(BaseModel):
    scheduled_activity_id: str
    activity_title: str
    deadline_date: str | None
    overall_total: int
    overall_reported: int
    overall_pct: float
    by_district: list[ComplianceByDistrict]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _template_to_response(t: ActivityTemplate, times_used: int = 0) -> ActivityTemplateResponse:
    return ActivityTemplateResponse(
        id=str(t.id),
        title_kn=t.title_kn,
        title_en=t.title_en,
        description_kn=t.description_kn,
        category=t.category,
        age_group=t.age_group,
        difficulty=t.difficulty,
        duration_minutes=t.duration_minutes,
        min_children=t.min_children,
        max_children=t.max_children,
        steps_kn=[s if isinstance(s, dict) else s for s in (t.steps_kn or [])],
        materials_kn=t.materials_kn,
        reference_image_urls=t.reference_image_urls or [],
        type=t.type,
        status=t.status,
        times_used=times_used,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


# ─── Activity Template routes ─────────────────────────────────────────────────

@router.get("/templates", response_model=ActivityTemplateListResponse)
async def list_templates(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    category: str = Query(""),
    status: str = Query(""),
    type: str = Query(""),
):
    stmt = select(ActivityTemplate)

    if search:
        from sqlalchemy import or_
        p = f"%{search}%"
        stmt = stmt.where(
            or_(ActivityTemplate.title_kn.ilike(p), ActivityTemplate.title_en.ilike(p))
        )
    if category:
        stmt = stmt.where(ActivityTemplate.category == category)
    if status:
        stmt = stmt.where(ActivityTemplate.status == status)
    else:
        # Default: hide archived
        stmt = stmt.where(ActivityTemplate.status != "archived")
    if type:
        stmt = stmt.where(ActivityTemplate.type == type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(ActivityTemplate.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    templates = (await db.execute(stmt)).scalars().all()

    # Batch: times_used per template
    if templates:
        t_ids = [t.id for t in templates]
        usage_stmt = (
            select(ActivityReport.activity_template_id, func.count().label("cnt"))
            .where(ActivityReport.activity_template_id.in_(t_ids))
            .group_by(ActivityReport.activity_template_id)
        )
        usage_rows = (await db.execute(usage_stmt)).all()
        usage_map = {str(r.activity_template_id): r.cnt for r in usage_rows}
    else:
        usage_map = {}

    return ActivityTemplateListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_template_to_response(t, usage_map.get(str(t.id), 0)) for t in templates],
    )


@router.post("/templates", response_model=ActivityTemplateResponse, status_code=201)
async def create_template(
    body: ActivityTemplateCreate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    if body.status not in ("draft", "published", "archived"):
        raise HTTPException(400, "status must be draft | published | archived")

    t = ActivityTemplate(
        title_kn=body.title_kn,
        title_en=body.title_en,
        description_kn=body.description_kn,
        category=body.category,
        age_group=body.age_group,
        difficulty=body.difficulty,
        duration_minutes=body.duration_minutes,
        min_children=body.min_children,
        max_children=body.max_children,
        steps_kn=[s.model_dump() for s in body.steps_kn],
        materials_kn=body.materials_kn,
        reference_image_urls=body.reference_image_urls,
        type=body.type,
        status=body.status,
        approved=(body.status == "published"),
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    logger.info("ActivityTemplate created: %s by admin %s", t.id, admin.email)
    return _template_to_response(t)


@router.get("/templates/{template_id}", response_model=ActivityTemplateResponse)
async def get_template(
    template_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ActivityTemplate).where(ActivityTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Activity template not found")

    usage_result = await db.execute(
        select(func.count()).where(ActivityReport.activity_template_id == template_id)
    )
    times_used = usage_result.scalar() or 0
    return _template_to_response(t, times_used)


@router.put("/templates/{template_id}", response_model=ActivityTemplateResponse)
async def update_template(
    template_id: UUID,
    body: ActivityTemplateUpdate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ActivityTemplate).where(ActivityTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Activity template not found")

    update_data = body.model_dump(exclude_none=True)
    if "steps_kn" in update_data:
        update_data["steps_kn"] = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in body.steps_kn
        ]
    if "status" in update_data:
        update_data["approved"] = (update_data["status"] == "published")

    for field, value in update_data.items():
        setattr(t, field, value)

    await db.commit()
    await db.refresh(t)
    return _template_to_response(t)


@router.delete("/templates/{template_id}", status_code=204)
async def archive_template(
    template_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete — sets status to archived."""
    result = await db.execute(select(ActivityTemplate).where(ActivityTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Activity template not found")
    t.status = "archived"
    t.approved = False
    await db.commit()


# ─── AI Suggest route ─────────────────────────────────────────────────────────

class AISuggestRequest(BaseModel):
    category: str
    age_group: str
    season: str | None = None
    recent_titles: list[str] = []


@router.post("/templates/ai-suggest")
async def ai_suggest_template(
    body: AISuggestRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
):
    """
    Call Gemini to generate a new activity template suggestion.
    Returns a draft payload — does NOT auto-save to DB.
    The frontend pre-fills the Activity Editor with the result.
    """
    try:
        result = await gemini_suggest_activity(
            category=body.category,
            age_group=body.age_group,
            season=body.season,
            recent_titles=body.recent_titles,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


# ─── Scheduled Activity routes ────────────────────────────────────────────────

@router.get("/scheduled", response_model=list[ScheduledActivityResponse])
async def list_scheduled(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    upcoming_only: bool = Query(False),
):
    stmt = select(ScheduledActivity, ActivityTemplate.title_kn).join(
        ActivityTemplate, ScheduledActivity.activity_template_id == ActivityTemplate.id
    )
    if upcoming_only:
        stmt = stmt.where(
            ScheduledActivity.deadline_date >= date.today()
        )
    stmt = stmt.order_by(ScheduledActivity.deadline_date.asc().nullslast())
    rows = (await db.execute(stmt)).all()

    return [
        ScheduledActivityResponse(
            id=str(sa.id),
            activity_template_id=str(sa.activity_template_id),
            activity_title=title_kn,
            scheduled_date=sa.scheduled_date,
            deadline_date=sa.deadline_date,
            is_mandatory=sa.is_mandatory,
            target_scope=sa.target_scope,
            target_filter=sa.target_filter,
            circular_reference=sa.circular_reference,
            immediate_sent=sa.immediate_sent,
            notification_sent=sa.notification_sent,
            reminder_sent=sa.reminder_sent,
            created_at=sa.created_at,
        )
        for sa, title_kn in rows
    ]


@router.post("/scheduled", response_model=ScheduledActivityResponse, status_code=201)
async def schedule_activity(
    body: ScheduleActivityRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    # Verify template exists and is published
    t_result = await db.execute(
        select(ActivityTemplate).where(ActivityTemplate.id == body.activity_template_id)
    )
    template = t_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(404, "Activity template not found")
    if template.status == "archived":
        raise HTTPException(400, "Cannot schedule an archived template")

    if body.target_scope not in ("all", "district", "taluk"):
        raise HTTPException(400, "target_scope must be all | district | taluk")

    sa = ScheduledActivity(
        activity_template_id=body.activity_template_id,
        scheduled_date=body.scheduled_date,
        deadline_date=body.deadline_date,
        is_mandatory=True,
        target_scope=body.target_scope,
        target_filter=body.target_filter,
        circular_reference=body.circular_reference,
        created_by_id=admin.id,
    )
    db.add(sa)
    await db.commit()
    await db.refresh(sa)

    # TODO Phase 4: if notify_immediately → dispatch Whatomate messages to all librarians in scope
    logger.info(
        "ScheduledActivity created: %s template=%s scope=%s by=%s",
        sa.id, body.activity_template_id, body.target_scope, admin.email,
    )

    return ScheduledActivityResponse(
        id=str(sa.id),
        activity_template_id=str(sa.activity_template_id),
        activity_title=template.title_kn,
        scheduled_date=sa.scheduled_date,
        deadline_date=sa.deadline_date,
        is_mandatory=sa.is_mandatory,
        target_scope=sa.target_scope,
        target_filter=sa.target_filter,
        circular_reference=sa.circular_reference,
        immediate_sent=sa.immediate_sent,
        notification_sent=sa.notification_sent,
        reminder_sent=sa.reminder_sent,
        created_at=sa.created_at,
    )


@router.delete("/scheduled/{scheduled_id}", status_code=204)
async def cancel_scheduled(
    scheduled_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ScheduledActivity).where(ScheduledActivity.id == scheduled_id))
    sa = result.scalar_one_or_none()
    if sa is None:
        raise HTTPException(404, "Scheduled activity not found")
    await db.delete(sa)
    await db.commit()


# ─── Compliance route ─────────────────────────────────────────────────────────

@router.get("/compliance/{scheduled_id}", response_model=ComplianceResponse)
async def get_compliance(
    scheduled_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    # Load the scheduled activity + template title
    result = await db.execute(
        select(ScheduledActivity, ActivityTemplate.title_kn).join(
            ActivityTemplate, ScheduledActivity.activity_template_id == ActivityTemplate.id
        ).where(ScheduledActivity.id == scheduled_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(404, "Scheduled activity not found")
    sa, activity_title = row

    # Apply district filter for coordinators
    allowed_districts = district_filter(admin)

    # Determine in-scope librarians
    lib_stmt = select(Librarian).where(Librarian.status == "onboarded")
    if sa.target_scope == "district" and sa.target_filter:
        districts = sa.target_filter.get("districts", [])
        lib_stmt = lib_stmt.where(Librarian.district.in_(districts))
    elif sa.target_scope == "taluk" and sa.target_filter:
        taluks = sa.target_filter.get("taluks", [])
        lib_stmt = lib_stmt.where(Librarian.taluk.in_(taluks))

    if allowed_districts is not None:
        lib_stmt = lib_stmt.where(Librarian.district.in_(allowed_districts))

    librarians = (await db.execute(lib_stmt)).scalars().all()
    lib_id_set = {lib.id for lib in librarians}

    # Librarians who reported for this scheduled activity
    reported_stmt = (
        select(ActivityReport.librarian_id)
        .where(ActivityReport.scheduled_activity_id == scheduled_id)
        .where(ActivityReport.librarian_id.in_(lib_id_set))
    )
    reported_ids = set((await db.execute(reported_stmt)).scalars().all())

    # Build per-district breakdown
    district_map: dict[str, dict] = {}
    for lib in librarians:
        d = lib.district or "Unknown"
        if d not in district_map:
            district_map[d] = {"total": 0, "reported": 0}
        district_map[d]["total"] += 1
        if lib.id in reported_ids:
            district_map[d]["reported"] += 1

    by_district = [
        ComplianceByDistrict(
            district=d,
            total_librarians=v["total"],
            reported_count=v["reported"],
            compliance_pct=round(v["reported"] / v["total"] * 100, 1) if v["total"] else 0.0,
        )
        for d, v in sorted(district_map.items())
    ]

    overall_total = len(librarians)
    overall_reported = len(reported_ids)

    return ComplianceResponse(
        scheduled_activity_id=str(scheduled_id),
        activity_title=activity_title,
        deadline_date=str(sa.deadline_date) if sa.deadline_date else None,
        overall_total=overall_total,
        overall_reported=overall_reported,
        overall_pct=round(overall_reported / overall_total * 100, 1) if overall_total else 0.0,
        by_district=by_district,
    )


# ─── Special Days routes ──────────────────────────────────────────────────────

class SpecialDayResponse(BaseModel):
    id: str
    month: int
    day: int
    year: int | None
    occasion_kn: str
    occasion_en: str
    is_system: bool


class SpecialDayCreate(BaseModel):
    month: int
    day: int
    year: int | None = None
    occasion_kn: str
    occasion_en: str


@router.get("/special-days", response_model=list[SpecialDayResponse])
async def list_special_days(
    year: int = Query(default=0),
    admin: Annotated[AdminUser, Depends(get_current_admin)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return all special days for a given year: system recurring + custom for that year."""
    from sqlalchemy import or_
    target_year = year if year else date.today().year
    stmt = (
        select(SpecialDay)
        .where(or_(SpecialDay.year.is_(None), SpecialDay.year == target_year))
        .order_by(SpecialDay.month, SpecialDay.day)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SpecialDayResponse(
            id=str(r.id), month=r.month, day=r.day, year=r.year,
            occasion_kn=r.occasion_kn, occasion_en=r.occasion_en, is_system=r.is_system,
        )
        for r in rows
    ]


@router.post("/special-days", response_model=SpecialDayResponse, status_code=201)
async def create_special_day(
    body: SpecialDayCreate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Add a custom special day for a date (admin-defined, not pre-seeded)."""
    sd = SpecialDay(
        month=body.month,
        day=body.day,
        year=body.year,
        occasion_kn=body.occasion_kn,
        occasion_en=body.occasion_en,
        is_system=False,
        created_by_id=admin.id,
    )
    db.add(sd)
    await db.commit()
    await db.refresh(sd)
    return SpecialDayResponse(
        id=str(sd.id), month=sd.month, day=sd.day, year=sd.year,
        occasion_kn=sd.occasion_kn, occasion_en=sd.occasion_en, is_system=sd.is_system,
    )


@router.delete("/special-days/{day_id}", status_code=204)
async def delete_special_day(
    day_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Delete an admin-created special day. System days cannot be deleted."""
    result = await db.execute(select(SpecialDay).where(SpecialDay.id == day_id))
    sd = result.scalar_one_or_none()
    if sd is None:
        raise HTTPException(404, "Special day not found")
    if sd.is_system:
        raise HTTPException(403, "Cannot delete system special days")
    await db.delete(sd)
    await db.commit()


# ─── Occasion-based AI suggestions ───────────────────────────────────────────

class SuggestForOccasionRequest(BaseModel):
    occasion: str
    occasion_date: str  # ISO date string e.g. "2026-03-08"


@router.post("/templates/suggest-for-occasion")
async def suggest_for_occasion(
    body: SuggestForOccasionRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
):
    """
    Generate 4 activity drafts themed around a special occasion.
    Returns list of activity dicts — NOT saved to DB.
    """
    try:
        result = await suggest_activities_for_occasion(
            occasion=body.occasion,
            occasion_date=body.occasion_date,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


# ─── Push selected activities to a Circular ──────────────────────────────────

class ActivityDraftIn(BaseModel):
    title_kn: str
    title_en: str | None = None
    description_kn: str | None = None
    category: str | None = None
    age_group: str | None = None
    difficulty: str | None = None
    duration_minutes: int | None = None
    steps_kn: list[StepSchema] = []
    materials_kn: str | None = None
    is_mandatory: bool = True


class PushToCircularRequest(BaseModel):
    circular_number: str
    issue_date: date | None = None
    occasion: str
    activities: list[ActivityDraftIn]


@router.post("/push-to-circular", status_code=201)
async def push_to_circular(
    body: PushToCircularRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """
    Save selected activity drafts as published templates, then create a Circular
    with CircularActionItems linked to each template (mandatory or optional).
    Returns the created circular id and number.
    """
    import uuid as _uuid

    if not body.activities:
        raise HTTPException(400, "At least one activity is required")

    # 1. Save each selected activity as a template
    saved_templates: list[tuple[ActivityTemplate, bool]] = []
    for act in body.activities:
        t = ActivityTemplate(
            title_kn=act.title_kn,
            title_en=act.title_en,
            description_kn=act.description_kn,
            category=act.category,
            age_group=act.age_group,
            difficulty=act.difficulty,
            duration_minutes=act.duration_minutes,
            steps_kn=[s.model_dump() for s in act.steps_kn],
            materials_kn=act.materials_kn,
            type="regular",
            status="published",
            approved=True,
        )
        db.add(t)
        await db.flush()  # get t.id
        saved_templates.append((t, act.is_mandatory))

    # 2. Create the circular
    c = Circular(
        id=_uuid.uuid4(),
        circular_number=body.circular_number,
        issue_date=body.issue_date,
        original_text=f"Activities for {body.occasion}",
        simplified_text=f"ಚಟುವಟಿಕೆಗಳು - {body.occasion}",
        status="draft",
        created_by_id=admin.id,
    )
    db.add(c)
    await db.flush()

    # 3. Add action items
    for i, (template, is_mandatory) in enumerate(saved_templates):
        item = CircularActionItem(
            id=_uuid.uuid4(),
            circular_id=c.id,
            activity_template_id=template.id,
            title_kn=template.title_kn,
            order=i,
            mandatory=is_mandatory,
        )
        db.add(item)

    await db.commit()
    logger.info(
        "push_to_circular: circular=%s occasion=%s activities=%d by=%s",
        c.circular_number, body.occasion, len(saved_templates), admin.email,
    )
    return {
        "circular_id": str(c.id),
        "circular_number": c.circular_number,
        "activities_saved": len(saved_templates),
        "status": "draft",
    }
