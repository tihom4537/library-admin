"""
Admin — CSV Export

Download portal data as CSV files for offline analysis.

  GET /admin/export/librarians    All librarians (name, district, status, last active, etc.)
  GET /admin/export/reports       Activity reports (date range, district filters optional)
  GET /admin/export/compliance    Compliance summary per district per mandatory activity
"""
import io
import logging
from datetime import date, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin
from app.db.database import get_db
from app.models.activity import ActivityReport, ActivityTemplate, ScheduledActivity
from app.models.admin import AdminUser
from app.models.librarian import Librarian

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["admin-export"])


def _csv_response(df: pd.DataFrame, filename: str) -> StreamingResponse:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(
        io.BytesIO(buffer.getvalue().encode("utf-8-sig")),  # utf-8-sig for Excel BOM
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/librarians")
async def export_librarians(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    status: str = Query(""),
):
    """Download all librarians as CSV."""
    allowed_districts = district_filter(admin)

    stmt = select(Librarian)
    if status:
        stmt = stmt.where(Librarian.status == status)
    if allowed_districts is not None:
        stmt = stmt.where(Librarian.district.in_(allowed_districts))
    stmt = stmt.order_by(Librarian.district, Librarian.name)

    librarians = (await db.execute(stmt)).scalars().all()

    rows = [
        {
            "id": str(lib.id),
            "name": lib.name,
            "phone": lib.phone,
            "library_name": lib.library_name,
            "library_id": lib.library_id,
            "district": lib.district,
            "taluk": lib.taluk,
            "gram_panchayat": lib.gram_panchayat,
            "status": lib.status,
            "language_pref": lib.language_pref,
            "onboarded_at": lib.onboarded_at.isoformat() if lib.onboarded_at else "",
            "last_active_at": lib.last_active_at.isoformat() if lib.last_active_at else "",
        }
        for lib in librarians
    ]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "name", "phone", "library_name", "library_id",
                 "district", "taluk", "gram_panchayat", "status",
                 "language_pref", "onboarded_at", "last_active_at"]
    )
    today = date.today().isoformat()
    logger.info("CSV export: librarians (%d rows) by %s", len(rows), admin.email)
    return _csv_response(df, f"librarians_{today}.csv")


@router.get("/reports")
async def export_reports(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    from_date: str = Query("", description="YYYY-MM-DD"),
    to_date: str = Query("", description="YYYY-MM-DD"),
    district: str = Query(""),
):
    """Download activity reports as CSV with optional date and district filters."""
    allowed_districts = district_filter(admin)

    stmt = (
        select(
            ActivityReport,
            Librarian.name.label("librarian_name"),
            Librarian.district.label("district"),
            Librarian.library_name.label("library_name"),
        )
        .join(Librarian, ActivityReport.librarian_id == Librarian.id, isouter=True)
    )

    if from_date:
        try:
            stmt = stmt.where(ActivityReport.created_at >= datetime.fromisoformat(from_date))
        except ValueError:
            pass
    if to_date:
        try:
            stmt = stmt.where(ActivityReport.created_at <= datetime.fromisoformat(to_date + "T23:59:59"))
        except ValueError:
            pass
    if district:
        stmt = stmt.where(Librarian.district == district)
    if allowed_districts is not None:
        stmt = stmt.where(Librarian.district.in_(allowed_districts))

    stmt = stmt.order_by(ActivityReport.created_at.desc())
    rows_result = (await db.execute(stmt)).all()

    rows = [
        {
            "report_id": str(r.ActivityReport.id),
            "librarian_name": r.librarian_name or "",
            "library_name": r.library_name or "",
            "district": r.district or "",
            "activity_title": r.ActivityReport.activity_title or "",
            "conducted_date": str(r.ActivityReport.conducted_date) if r.ActivityReport.conducted_date else "",
            "children_count": r.ActivityReport.approximate_children_count or "",
            "feedback": r.ActivityReport.librarian_feedback or "",
            "photos_count": len(r.ActivityReport.photo_urls) if r.ActivityReport.photo_urls else 0,
            "reported_via": r.ActivityReport.reported_via,
            "note": r.ActivityReport.optional_note or "",
            "submitted_at": r.ActivityReport.created_at.isoformat(),
        }
        for r in rows_result
    ]

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["report_id", "librarian_name", "library_name", "district",
                 "activity_title", "conducted_date", "children_count",
                 "feedback", "photos_count", "reported_via", "note", "submitted_at"]
    )
    today = date.today().isoformat()
    logger.info("CSV export: reports (%d rows) by %s", len(rows), admin.email)
    return _csv_response(df, f"activity_reports_{today}.csv")


@router.get("/compliance")
async def export_compliance(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    """
    Download compliance summary: per mandatory activity per district.
    Shows total librarians in scope, how many reported, and compliance %.
    """
    allowed_districts = district_filter(admin)

    # Get all mandatory scheduled activities
    scheduled_result = await db.execute(
        select(ScheduledActivity, ActivityTemplate.title_kn)
        .join(ActivityTemplate, ScheduledActivity.activity_template_id == ActivityTemplate.id)
        .where(ScheduledActivity.is_mandatory == True)
        .order_by(ScheduledActivity.deadline_date.desc().nullslast())
    )
    scheduled_rows = scheduled_result.all()

    # Get all onboarded librarians
    lib_stmt = select(Librarian).where(Librarian.status == "onboarded")
    if allowed_districts is not None:
        lib_stmt = lib_stmt.where(Librarian.district.in_(allowed_districts))
    librarians = (await db.execute(lib_stmt)).scalars().all()

    # Pre-load all reports for mandatory activities
    mandatory_ids = [sa.id for sa, _ in scheduled_rows]
    if mandatory_ids:
        reports_result = await db.execute(
            select(ActivityReport.scheduled_activity_id, ActivityReport.librarian_id)
            .where(ActivityReport.scheduled_activity_id.in_(mandatory_ids))
        )
        # Map: scheduled_activity_id → set of librarian_ids who reported
        reported_map: dict = {}
        for sa_id, lib_id in reports_result.all():
            reported_map.setdefault(sa_id, set()).add(lib_id)
    else:
        reported_map = {}

    rows = []
    for sa, title_kn in scheduled_rows:
        # Group librarians by district
        district_map: dict[str, list] = {}
        for lib in librarians:
            if sa.target_scope == "district" and sa.target_filter:
                if lib.district not in sa.target_filter.get("districts", []):
                    continue
            d = lib.district or "Unknown"
            district_map.setdefault(d, []).append(lib.id)

        reported_ids = reported_map.get(sa.id, set())
        for district, lib_ids in sorted(district_map.items()):
            total = len(lib_ids)
            reported = sum(1 for lid in lib_ids if lid in reported_ids)
            rows.append({
                "activity_title": title_kn,
                "scheduled_activity_id": str(sa.id),
                "deadline_date": str(sa.deadline_date) if sa.deadline_date else "",
                "target_scope": sa.target_scope,
                "district": district,
                "total_librarians": total,
                "reported_count": reported,
                "compliance_pct": round(reported / total * 100, 1) if total else 0.0,
            })

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["activity_title", "scheduled_activity_id", "deadline_date",
                 "target_scope", "district", "total_librarians",
                 "reported_count", "compliance_pct"]
    )
    today = date.today().isoformat()
    logger.info("CSV export: compliance (%d rows) by %s", len(rows), admin.email)
    return _csv_response(df, f"compliance_{today}.csv")
