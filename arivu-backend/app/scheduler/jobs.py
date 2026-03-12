"""
Background scheduler jobs.

compute_dashboard_stats() — runs every 5 minutes.
  Queries the DB once, writes results to Redis.
  Dashboard endpoints read from Redis only — never hit DB directly.

generate_weekly_nudge_drafts() — runs every Sunday at 08:00.
  Calls Gemini to generate two nudge drafts for the coming week.
  Saves them as 'draft' WeeklyNudge records for admin review.

Redis keys:
  arivu:dashboard:stats       → JSON dict (5-min TTL)
  arivu:dashboard:inactive    → JSON list of librarian IDs (5-min TTL)
"""
import json
import logging
from datetime import date, datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.activity import ActivityReport, ScheduledActivity
from app.models.admin import WeeklyNudge
from app.models.librarian import Librarian

logger = logging.getLogger(__name__)

STATS_KEY = "arivu:dashboard:stats"
INACTIVE_KEY = "arivu:dashboard:inactive"
CACHE_TTL = 5 * 60  # 5 minutes


async def compute_dashboard_stats() -> None:
    """
    Compute dashboard statistics and write to Redis.
    Called by APScheduler every 5 minutes and once at startup.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cutoff_7d = now - timedelta(days=7)
            cutoff_30d = now - timedelta(days=30)

            # ── active librarians (last_active_at within 7 days) ────────────
            active_count = (await db.execute(
                select(func.count()).where(
                    Librarian.status == "onboarded",
                    Librarian.last_active_at >= cutoff_7d,
                )
            )).scalar() or 0

            # ── reports this month ──────────────────────────────────────────
            reports_month = (await db.execute(
                select(func.count()).where(
                    ActivityReport.created_at >= month_start
                )
            )).scalar() or 0

            # ── photos count (sum of photo_urls array lengths) ──────────────
            # JSONB array; use jsonb_array_length and coalesce nulls to 0
            photos_count = (await db.execute(
                text(
                    "SELECT COALESCE(SUM(jsonb_array_length(photo_urls)), 0) "
                    "FROM activity_report "
                    "WHERE photo_urls IS NOT NULL AND jsonb_typeof(photo_urls) = 'array'"
                )
            )).scalar() or 0

            # ── mandatory compliance % (last 30 days) ───────────────────────
            # Find mandatory scheduled activities with deadline in last 30 days
            mandatory_ids_result = await db.execute(
                select(ScheduledActivity.id).where(
                    ScheduledActivity.is_mandatory == True,
                    ScheduledActivity.deadline_date >= (now - timedelta(days=30)).date(),
                )
            )
            mandatory_ids = [r[0] for r in mandatory_ids_result.all()]

            mandatory_compliance_pct = 0.0
            if mandatory_ids:
                total_onboarded = (await db.execute(
                    select(func.count()).where(Librarian.status == "onboarded")
                )).scalar() or 0

                if total_onboarded > 0:
                    # Distinct librarians who submitted at least one report for any mandatory activity
                    reported_count = (await db.execute(
                        select(func.count(ActivityReport.librarian_id.distinct())).where(
                            ActivityReport.scheduled_activity_id.in_(mandatory_ids)
                        )
                    )).scalar() or 0
                    mandatory_compliance_pct = round(reported_count / total_onboarded * 100, 1)

            # ── inactive librarians (onboarded, no report in 30 days) ───────
            # Librarians who have been onboarded but submitted no report in the last 30 days
            reported_recently_result = await db.execute(
                select(ActivityReport.librarian_id.distinct()).where(
                    ActivityReport.created_at >= cutoff_30d
                )
            )
            reported_recently_ids = {r[0] for r in reported_recently_result.all()}

            all_onboarded_result = await db.execute(
                select(Librarian.id, Librarian.name, Librarian.district, Librarian.phone).where(
                    Librarian.status == "onboarded"
                )
            )
            inactive_list = [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "district": r.district,
                    "phone": r.phone,
                }
                for r in all_onboarded_result.all()
                if r.id not in reported_recently_ids
            ]

            stats = {
                "active_librarians_count": active_count,
                "reports_this_month": reports_month,
                "photos_count": int(photos_count),
                "mandatory_compliance_pct": mandatory_compliance_pct,
                "inactive_librarians_count": len(inactive_list),
                "computed_at": now.isoformat(),
            }

        # Write to Redis
        redis_client = await aioredis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        try:
            await redis_client.setex(STATS_KEY, CACHE_TTL, json.dumps(stats))
            await redis_client.setex(INACTIVE_KEY, CACHE_TTL, json.dumps(inactive_list))
            logger.info(
                "Dashboard stats refreshed: active=%d reports=%d compliance=%.1f%%",
                active_count, reports_month, mandatory_compliance_pct,
            )
        finally:
            await redis_client.aclose()

    except Exception as e:
        logger.error("compute_dashboard_stats failed: %s", e, exc_info=True)
    finally:
        await engine.dispose()


async def generate_weekly_nudge_drafts() -> None:
    """
    Generate AI nudge drafts for the coming week.
    Called every Sunday at 08:00 by APScheduler.
    Creates two WeeklyNudge records (status='draft') if they don't exist yet.
    """
    from app.ai.gemini import generate_weekly_nudge

    # Next Monday is the week_start_date
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_until_monday)

    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with AsyncSessionLocal() as db:
            for nudge_type in ("monday_activity", "thursday_motivational"):
                # Skip if already exists for this week
                existing = (await db.execute(
                    select(WeeklyNudge).where(
                        WeeklyNudge.week_start_date == next_monday,
                        WeeklyNudge.nudge_type == nudge_type,
                    )
                )).scalar_one_or_none()

                if existing:
                    logger.info(
                        "Nudge draft already exists for %s %s — skipping",
                        next_monday, nudge_type,
                    )
                    continue

                try:
                    result = await generate_weekly_nudge(
                        nudge_type=nudge_type,
                        week_start_date=next_monday.isoformat(),
                    )
                    nudge = WeeklyNudge(
                        week_start_date=next_monday,
                        nudge_type=nudge_type,
                        content_kn=result.get("content_kn", ""),
                        content_en=result.get("content_en"),
                        status="draft",
                        generated_by="ai",
                    )
                    db.add(nudge)
                    logger.info(
                        "AI nudge draft created: %s for week %s", nudge_type, next_monday
                    )
                except Exception as e:
                    logger.error(
                        "Failed to generate nudge draft %s for %s: %s",
                        nudge_type, next_monday, e,
                    )

            await db.commit()

    except Exception as e:
        logger.error("generate_weekly_nudge_drafts failed: %s", e, exc_info=True)
    finally:
        await engine.dispose()
