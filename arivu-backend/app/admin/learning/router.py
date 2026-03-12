"""
Admin — Micro-Learning Module Manager

3-step WhatsApp micro-learning lessons sent to librarians weekly.
AI can break down any pasted text into a ready-to-send module.

  GET    /admin/learning/modules                  paginated list
  POST   /admin/learning/modules                  create module
  POST   /admin/learning/modules/ai-breakdown     AI-generate from pasted text (no save)
  GET    /admin/learning/modules/{id}             detail
  PUT    /admin/learning/modules/{id}             update
  DELETE /admin/learning/modules/{id}             deactivate (soft delete)
  POST   /admin/learning/modules/{id}/publish     toggle published
  POST   /admin/learning/modules/{id}/send        send to all onboarded librarians
  GET    /admin/learning/modules/{id}/progress    completion stats per district
"""
import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin, require_role
from app.ai.gemini import breakdown_pdf_content
from app.db.database import get_db
from app.models.activity import LibrarianLearningProgress, MicroLearningModule
from app.models.admin import AdminUser
from app.models.librarian import Librarian
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/learning", tags=["admin-learning"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ModuleCreate(BaseModel):
    title_kn: str
    category: str | None = None          # computer | library | reading | craft | other
    difficulty: str = "beginner"          # beginner | intermediate | advanced
    estimated_minutes: int = 5
    sequence_order: int = 0
    step_one_heading_kn: str | None = None
    step_one_text_kn: str | None = None
    step_one_image_url: str | None = None
    step_two_heading_kn: str | None = None
    step_two_text_kn: str | None = None
    step_two_image_url: str | None = None
    step_three_heading_kn: str | None = None
    step_three_text_kn: str | None = None
    step_three_image_url: str | None = None
    practice_prompt_kn: str | None = None


class ModuleUpdate(BaseModel):
    title_kn: str | None = None
    category: str | None = None
    difficulty: str | None = None
    estimated_minutes: int | None = None
    sequence_order: int | None = None
    step_one_heading_kn: str | None = None
    step_one_text_kn: str | None = None
    step_one_image_url: str | None = None
    step_two_heading_kn: str | None = None
    step_two_text_kn: str | None = None
    step_two_image_url: str | None = None
    step_three_heading_kn: str | None = None
    step_three_text_kn: str | None = None
    step_three_image_url: str | None = None
    practice_prompt_kn: str | None = None
    published: bool | None = None


class AIBreakdownRequest(BaseModel):
    text: str
    topic: str | None = None


class ModuleResponse(BaseModel):
    id: str
    title_kn: str
    category: str | None
    difficulty: str
    estimated_minutes: int
    sequence_order: int
    active: bool
    published: bool
    step_one_heading_kn: str | None
    step_one_text_kn: str | None
    step_one_image_url: str | None
    step_two_heading_kn: str | None
    step_two_text_kn: str | None
    step_two_image_url: str | None
    step_three_heading_kn: str | None
    step_three_text_kn: str | None
    step_three_image_url: str | None
    practice_prompt_kn: str | None
    created_at: datetime
    updated_at: datetime


class ModuleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ModuleResponse]


class SendResponse(BaseModel):
    attempted: int
    succeeded: int
    failed: int


class ProgressByDistrict(BaseModel):
    district: str
    sent_count: int
    viewed_count: int
    practice_completed_count: int
    completion_pct: float


class ModuleProgressResponse(BaseModel):
    module_id: str
    module_title: str
    total_sent: int
    total_viewed: int
    total_practice_completed: int
    by_district: list[ProgressByDistrict]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _to_response(m: MicroLearningModule) -> ModuleResponse:
    return ModuleResponse(
        id=str(m.id),
        title_kn=m.title_kn,
        category=m.category,
        difficulty=m.difficulty,
        estimated_minutes=m.estimated_minutes,
        sequence_order=m.sequence_order,
        active=m.active,
        published=m.published,
        step_one_heading_kn=m.step_one_heading_kn,
        step_one_text_kn=m.step_one_text_kn,
        step_one_image_url=m.step_one_image_url,
        step_two_heading_kn=m.step_two_heading_kn,
        step_two_text_kn=m.step_two_text_kn,
        step_two_image_url=m.step_two_image_url,
        step_three_heading_kn=m.step_three_heading_kn,
        step_three_text_kn=m.step_three_text_kn,
        step_three_image_url=m.step_three_image_url,
        practice_prompt_kn=m.practice_prompt_kn,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/modules", response_model=ModuleListResponse)
async def list_modules(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    published: str = Query(""),   # "true" | "false" | ""
    category: str = Query(""),
    search: str = Query(""),
):
    stmt = select(MicroLearningModule).where(MicroLearningModule.active == True)

    if published == "true":
        stmt = stmt.where(MicroLearningModule.published == True)
    elif published == "false":
        stmt = stmt.where(MicroLearningModule.published == False)
    if category:
        stmt = stmt.where(MicroLearningModule.category == category)
    if search:
        stmt = stmt.where(MicroLearningModule.title_kn.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(MicroLearningModule.sequence_order.asc(), MicroLearningModule.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    modules = (await db.execute(stmt)).scalars().all()

    return ModuleListResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(m) for m in modules],
    )


@router.post("/modules", response_model=ModuleResponse, status_code=201)
async def create_module(
    body: ModuleCreate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    m = MicroLearningModule(**body.model_dump())
    db.add(m)
    await db.commit()
    await db.refresh(m)
    logger.info("MicroLearningModule created: %s by %s", m.id, admin.email)
    return _to_response(m)


@router.post("/modules/ai-breakdown")
async def ai_breakdown(
    body: AIBreakdownRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
):
    """
    Use Gemini to convert pasted text into a 3-step module draft.
    Returns a draft payload — does NOT auto-save to DB.
    Frontend pre-fills the Module Editor with the result.
    """
    if len(body.text.strip()) < 20:
        raise HTTPException(400, "Text is too short to break down")
    try:
        return await breakdown_pdf_content(body.text, body.topic)
    except ValueError as e:
        raise HTTPException(502, f"AI error: {e}")


@router.get("/modules/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")
    return _to_response(m)


@router.put("/modules/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: UUID,
    body: ModuleUpdate,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(m, field, value)

    await db.commit()
    await db.refresh(m)
    return _to_response(m)


@router.delete("/modules/{module_id}", status_code=204)
async def deactivate_module(
    module_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Soft delete — sets active=False."""
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")
    m.active = False
    m.published = False
    await db.commit()


@router.post("/modules/{module_id}/publish", response_model=ModuleResponse)
async def toggle_publish(
    module_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Toggle the published status of a module."""
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")
    m.published = not m.published
    await db.commit()
    await db.refresh(m)
    logger.info("Module %s published=%s by %s", module_id, m.published, admin.email)
    return _to_response(m)


@router.post("/modules/{module_id}/send", response_model=SendResponse)
async def send_module(
    module_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """
    Send the module to all onboarded librarians as a WhatsApp text message.
    Creates LibrarianLearningProgress records to track delivery.
    """
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")
    if not m.published:
        raise HTTPException(400, "Module must be published before sending")

    # Get all onboarded librarians
    libs_result = await db.execute(
        select(Librarian).where(
            Librarian.status == "onboarded",
            Librarian.phone.isnot(None),
        )
    )
    librarians = libs_result.scalars().all()

    # Build the message text
    parts = [f"📚 *{m.title_kn}*\n"]
    if m.step_one_heading_kn and m.step_one_text_kn:
        parts.append(f"*{m.step_one_heading_kn}*\n{m.step_one_text_kn}")
    if m.step_two_heading_kn and m.step_two_text_kn:
        parts.append(f"*{m.step_two_heading_kn}*\n{m.step_two_text_kn}")
    if m.step_three_heading_kn and m.step_three_text_kn:
        parts.append(f"*{m.step_three_heading_kn}*\n{m.step_three_text_kn}")
    if m.practice_prompt_kn:
        parts.append(f"✏️ *ಅಭ್ಯಾಸ:* {m.practice_prompt_kn}")
    message_text = "\n\n".join(parts)

    attempted = len(librarians)
    succeeded = 0
    failed = 0
    now = datetime.now(timezone.utc)

    for lib in librarians:
        try:
            await whatomate.send_text(contact_id=lib.phone, text=message_text)
            # Record delivery
            progress = LibrarianLearningProgress(
                librarian_id=lib.id,
                module_id=m.id,
                sent_at=now,
            )
            db.add(progress)
            succeeded += 1
        except Exception as e:
            logger.warning("Module send failed for %s: %s", lib.phone, e)
            failed += 1

    await db.commit()
    logger.info(
        "Module %s sent: %d/%d succeeded by %s",
        module_id, succeeded, attempted, admin.email,
    )
    return SendResponse(attempted=attempted, succeeded=succeeded, failed=failed)


@router.get("/modules/{module_id}/progress", response_model=ModuleProgressResponse)
async def get_module_progress(
    module_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Per-district completion stats for a module."""
    result = await db.execute(
        select(MicroLearningModule).where(MicroLearningModule.id == module_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Module not found")

    allowed_districts = district_filter(admin)

    # Join progress with librarian for district info
    prog_stmt = (
        select(LibrarianLearningProgress, Librarian.district)
        .join(Librarian, LibrarianLearningProgress.librarian_id == Librarian.id)
        .where(LibrarianLearningProgress.module_id == module_id)
    )
    if allowed_districts is not None:
        prog_stmt = prog_stmt.where(Librarian.district.in_(allowed_districts))

    rows = (await db.execute(prog_stmt)).all()

    district_map: dict[str, dict] = {}
    for prog, district in rows:
        d = district or "Unknown"
        if d not in district_map:
            district_map[d] = {"sent": 0, "viewed": 0, "practice": 0}
        district_map[d]["sent"] += 1
        if prog.viewed_at:
            district_map[d]["viewed"] += 1
        if prog.practice_completed:
            district_map[d]["practice"] += 1

    by_district = [
        ProgressByDistrict(
            district=d,
            sent_count=v["sent"],
            viewed_count=v["viewed"],
            practice_completed_count=v["practice"],
            completion_pct=round(v["practice"] / v["sent"] * 100, 1) if v["sent"] else 0.0,
        )
        for d, v in sorted(district_map.items())
    ]

    total_sent = sum(v["sent"] for v in district_map.values())
    total_viewed = sum(v["viewed"] for v in district_map.values())
    total_practice = sum(v["practice"] for v in district_map.values())

    return ModuleProgressResponse(
        module_id=str(module_id),
        module_title=m.title_kn,
        total_sent=total_sent,
        total_viewed=total_viewed,
        total_practice_completed=total_practice,
        by_district=by_district,
    )
