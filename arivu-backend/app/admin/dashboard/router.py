"""
Dashboard endpoints — all reads come from Redis cache (never DB directly).

GET  /admin/dashboard/stats     — 4 stat cards + computed_at timestamp
GET  /admin/dashboard/feed      — paginated recent activity reports with photos
GET  /admin/dashboard/inactive  — librarians with no report in 30 days
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin
from app.config import settings
from app.db.database import get_db
from app.models.activity import ActivityReport
from app.models.admin import AdminUser
from app.models.librarian import Librarian
from app.scheduler.jobs import INACTIVE_KEY, STATS_KEY

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    active_librarians_count: int
    reports_this_month: int
    photos_count: int
    mandatory_compliance_pct: float
    inactive_librarians_count: int
    computed_at: str


class FeedItem(BaseModel):
    report_id: str
    librarian_id: str
    librarian_name: str
    district: str | None
    activity_title: str | None
    conducted_date: str | None
    photo_urls: list[str]
    librarian_feedback: str | None
    reported_at: str


class InactiveLibrarian(BaseModel):
    id: str
    name: str
    district: str | None
    phone: str


# ── Redis helper ──────────────────────────────────────────────────────────────

async def _get_redis() -> aioredis.Redis:
    return await aioredis.from_url(
        settings.redis_url, encoding="utf-8", decode_responses=True
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    """
    Returns cached dashboard stats. Refreshed every 5 minutes by APScheduler.
    If cache is cold (first startup), returns zeros with a stale flag.
    """
    redis_client = await _get_redis()
    try:
        raw = await redis_client.get(STATS_KEY)
    finally:
        await redis_client.aclose()

    if not raw:
        # Cache cold — return empty stats rather than error
        return DashboardStats(
            active_librarians_count=0,
            reports_this_month=0,
            photos_count=0,
            mandatory_compliance_pct=0.0,
            inactive_librarians_count=0,
            computed_at="pending",
        )

    data = json.loads(raw)
    return DashboardStats(**data)


@router.get("/feed", response_model=list[FeedItem])
async def get_activity_feed(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    district: str = Query(""),
    photos_only: bool = Query(False, description="Only include reports with photos"),
):
    """
    Paginated recent activity reports with librarian details.
    Reads from DB (this is a feed, not a stat — caching would be stale too fast).
    Filtered by district for district_coordinator role.
    """
    allowed_districts = district_filter(admin)

    # Join reports with librarians
    stmt = (
        select(ActivityReport, Librarian.name, Librarian.district, Librarian.phone)
        .join(Librarian, ActivityReport.librarian_id == Librarian.id)
        .order_by(ActivityReport.created_at.desc())
    )

    if district:
        stmt = stmt.where(Librarian.district == district)
    elif allowed_districts is not None:
        stmt = stmt.where(Librarian.district.in_(allowed_districts))

    if photos_only:
        from sqlalchemy import text as sa_text
        stmt = stmt.where(
            ActivityReport.photo_urls.isnot(None),
            sa_text("jsonb_array_length(activity_report.photo_urls) > 0"),
        )

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    return [
        FeedItem(
            report_id=str(r.ActivityReport.id),
            librarian_id=str(r.ActivityReport.librarian_id),
            librarian_name=r.name,
            district=r.district,
            activity_title=r.ActivityReport.activity_title,
            conducted_date=str(r.ActivityReport.conducted_date) if r.ActivityReport.conducted_date else None,
            photo_urls=r.ActivityReport.photo_urls or [],
            librarian_feedback=r.ActivityReport.librarian_feedback,
            reported_at=r.ActivityReport.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/inactive", response_model=list[InactiveLibrarian])
async def get_inactive_librarians(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    district: str = Query(""),
):
    """
    Librarians with no activity report in the last 30 days.
    Reads from Redis cache. Filtered by district if coordinator.
    """
    redis_client = await _get_redis()
    try:
        raw = await redis_client.get(INACTIVE_KEY)
    finally:
        await redis_client.aclose()

    if not raw:
        return []

    all_inactive: list[dict] = json.loads(raw)
    allowed_districts = district_filter(admin)

    # Apply role-based district filter
    if allowed_districts is not None:
        all_inactive = [i for i in all_inactive if i.get("district") in allowed_districts]

    # Apply optional query district filter
    if district:
        all_inactive = [i for i in all_inactive if i.get("district") == district]

    return [InactiveLibrarian(**item) for item in all_inactive]
