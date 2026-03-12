"""
Circular Manager endpoints.

GET  /admin/circulars                — list with pagination + status filter
POST /admin/circulars                — create new circular
GET  /admin/circulars/{id}           — full detail including action items
PUT  /admin/circulars/{id}           — update text / status / action items
POST /admin/circulars/{id}/simplify  — call Gemini, return draft (does NOT auto-save)
POST /admin/circulars/{id}/send      — mark published + record sent_at (stub; actual
                                       dispatch is via Whatomate API in Phase 4)
"""
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_current_admin, require_role
from app.ai.gemini import simplify_circular
from app.db.database import get_db
from app.models.admin import AdminUser, Circular, CircularActionItem

router = APIRouter(prefix="/circulars", tags=["circulars"])

# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ActionItemIn(BaseModel):
    title_kn: str
    due_date: date | None = None
    order: int = 0
    activity_template_id: uuid.UUID | None = None


class CircularCreate(BaseModel):
    circular_number: str
    issue_date: date | None = None
    original_text: str | None = None
    simplified_text: str | None = None
    status: str = "draft"
    action_items: list[ActionItemIn] = []


class CircularUpdate(BaseModel):
    circular_number: str | None = None
    issue_date: date | None = None
    original_text: str | None = None
    simplified_text: str | None = None
    status: str | None = None
    action_items: list[ActionItemIn] | None = None  # None = don't replace


class ActionItemOut(BaseModel):
    id: uuid.UUID
    title_kn: str
    due_date: date | None
    order: int
    activity_template_id: uuid.UUID | None

    class Config:
        from_attributes = True


class CircularOut(BaseModel):
    id: uuid.UUID
    circular_number: str
    issue_date: date | None
    original_text: str | None
    simplified_text: str | None
    status: str
    created_by_id: uuid.UUID | None
    sent_at: datetime | None
    sent_count: int
    created_at: datetime
    updated_at: datetime
    action_items: list[ActionItemOut] = []

    class Config:
        from_attributes = True


class CircularListItem(BaseModel):
    id: uuid.UUID
    circular_number: str
    issue_date: date | None
    status: str
    action_item_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SimplifyResponse(BaseModel):
    simplified_kn: str
    action_items: list[dict]  # [{title_kn, due_date}]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_circular_or_404(circular_id: uuid.UUID, db: AsyncSession) -> Circular:
    result = await db.execute(select(Circular).where(Circular.id == circular_id))
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Circular not found")
    return c


async def _fetch_action_items(circular_id: uuid.UUID, db: AsyncSession) -> list[CircularActionItem]:
    result = await db.execute(
        select(CircularActionItem)
        .where(CircularActionItem.circular_id == circular_id)
        .order_by(CircularActionItem.order)
    )
    return list(result.scalars().all())


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CircularListItem])
async def list_circulars(
    status: str | None = Query(None, description="draft | published"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    q = select(
        Circular.id,
        Circular.circular_number,
        Circular.issue_date,
        Circular.status,
        Circular.created_at,
        func.count(CircularActionItem.id).label("action_item_count"),
    ).outerjoin(
        CircularActionItem, CircularActionItem.circular_id == Circular.id
    ).group_by(Circular.id)

    if status:
        q = q.where(Circular.status == status)

    q = q.order_by(Circular.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).all()

    return [
        CircularListItem(
            id=r.id,
            circular_number=r.circular_number,
            issue_date=r.issue_date,
            status=r.status,
            action_item_count=r.action_item_count,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("", response_model=CircularOut, status_code=status.HTTP_201_CREATED)
async def create_circular(
    body: CircularCreate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role("super_admin", "admin")),
):
    c = Circular(
        id=uuid.uuid4(),
        circular_number=body.circular_number,
        issue_date=body.issue_date,
        original_text=body.original_text,
        simplified_text=body.simplified_text,
        status=body.status,
        created_by_id=admin.id,
    )
    db.add(c)
    await db.flush()  # get c.id before adding action items

    items = []
    for ai in body.action_items:
        item = CircularActionItem(
            id=uuid.uuid4(),
            circular_id=c.id,
            title_kn=ai.title_kn,
            due_date=ai.due_date,
            order=ai.order,
            activity_template_id=ai.activity_template_id,
        )
        db.add(item)
        items.append(item)

    await db.commit()
    await db.refresh(c)
    out = CircularOut.model_validate(c)
    out.action_items = [ActionItemOut.model_validate(i) for i in items]
    return out


@router.get("/{circular_id}", response_model=CircularOut)
async def get_circular(
    circular_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    c = await _get_circular_or_404(circular_id, db)
    items = await _fetch_action_items(c.id, db)
    out = CircularOut.model_validate(c)
    out.action_items = [ActionItemOut.model_validate(i) for i in items]
    return out


@router.put("/{circular_id}", response_model=CircularOut)
async def update_circular(
    circular_id: uuid.UUID,
    body: CircularUpdate,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role("super_admin", "admin")),
):
    c = await _get_circular_or_404(circular_id, db)

    if body.circular_number is not None:
        c.circular_number = body.circular_number
    if body.issue_date is not None:
        c.issue_date = body.issue_date
    if body.original_text is not None:
        c.original_text = body.original_text
    if body.simplified_text is not None:
        c.simplified_text = body.simplified_text
    if body.status is not None:
        c.status = body.status

    # Replace action items if provided
    if body.action_items is not None:
        await db.execute(
            CircularActionItem.__table__.delete().where(
                CircularActionItem.circular_id == c.id
            )
        )
        for ai in body.action_items:
            db.add(CircularActionItem(
                id=uuid.uuid4(),
                circular_id=c.id,
                title_kn=ai.title_kn,
                due_date=ai.due_date,
                order=ai.order,
                activity_template_id=ai.activity_template_id,
            ))

    await db.commit()
    await db.refresh(c)
    items = await _fetch_action_items(c.id, db)
    out = CircularOut.model_validate(c)
    out.action_items = [ActionItemOut.model_validate(i) for i in items]
    return out


@router.post("/{circular_id}/simplify", response_model=SimplifyResponse)
async def simplify_circular_endpoint(
    circular_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role("super_admin", "admin")),
):
    """
    Call Gemini to simplify the circular's original_text.
    Returns a DRAFT — does NOT auto-save to DB.
    The frontend shows the result as editable text; admin saves via PUT /{id}.
    """
    c = await _get_circular_or_404(circular_id, db)
    if not c.original_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Circular has no original_text to simplify",
        )
    result = await simplify_circular(c.original_text)
    return SimplifyResponse(
        simplified_kn=result.get("simplified_kn", ""),
        action_items=result.get("action_items", []),
    )


@router.post("/{circular_id}/send")
async def send_circular(
    circular_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_role("super_admin", "admin")),
):
    """
    Mark circular as published and record sent_at timestamp.
    Actual WhatsApp dispatch via Whatomate is wired in Phase 4.
    """
    c = await _get_circular_or_404(circular_id, db)
    if c.status == "published":
        raise HTTPException(status_code=409, detail="Circular already sent")
    c.status = "published"
    c.sent_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "published", "sent_at": c.sent_at}
