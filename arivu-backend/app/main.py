"""
Arivu Kendra Bot — FastAPI Application
Receives messages from Whatomate and routes them to the appropriate flow handler.
"""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.database import create_tables
from app.scheduler.jobs import compute_dashboard_stats, generate_weekly_nudge_drafts
from app.session.manager import session_manager
from app.webhook.handler import router as webhook_router
from app.admin import admin_router

scheduler = AsyncIOScheduler()

# Import all models so SQLAlchemy registers them before create_tables() runs
import app.models.librarian  # noqa: F401
import app.models.activity   # noqa: F401
import app.models.support    # noqa: F401
import app.models.admin      # noqa: F401

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Arivu Kendra Bot...")

    # Connect Redis session manager
    await session_manager.connect()
    logger.info("Redis session manager connected")

    # Create tables (dev mode; use Alembic migrations in production)
    if settings.environment == "development":
        await create_tables()
        logger.info("Database tables created/verified")

    # Start background scheduler
    scheduler.add_job(
        compute_dashboard_stats,
        trigger="interval",
        minutes=5,
        id="dashboard_stats",
        replace_existing=True,
    )
    # Every Sunday at 08:00 — generate AI nudge drafts for the coming week
    scheduler.add_job(
        generate_weekly_nudge_drafts,
        trigger="cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id="weekly_nudge_drafts",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — dashboard stats every 5 min, nudge drafts every Sunday")

    # Warm up cache immediately on startup (don't wait 5 min for first read)
    try:
        await compute_dashboard_stats()
        logger.info("Dashboard stats cache warmed up")
    except Exception as e:
        logger.warning("Dashboard stats warm-up failed (non-fatal): %s", e)

    logger.info("Arivu backend ready on port %d", settings.port)
    yield

    # Shutdown
    logger.info("Shutting down Arivu backend...")
    scheduler.shutdown(wait=False)
    await session_manager.disconnect()


app = FastAPI(
    title="Arivu Kendra Bot",
    description="WhatsApp bot backend for Karnataka librarians",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Webhook route (WhatsApp bot)
app.include_router(webhook_router)

# Admin portal API
app.include_router(admin_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "arivu-backend"}


@app.get("/ready")
async def ready():
    # TODO: Add DB + Redis connectivity check
    return {"status": "ready"}
