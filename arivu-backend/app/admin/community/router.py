"""
Admin — Community Content Review

Librarians submit local stories, songs, games, crafts via WhatsApp.
Admins review, publish, or reject submissions here.

  GET    /admin/community                    list (filter: status, type, district, page)
  GET    /admin/community/{id}               detail
  PUT    /admin/community/{id}/status        update status: reviewed | published | rejected
  GET    /admin/community/{id}/audio         get pre-signed S3 URL for voice note
  POST   /admin/community/{id}/transcribe    transcribe voice note → description
"""
import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import district_filter, get_current_admin, require_role
from app.db.database import get_db
from app.models.admin import AdminUser
from app.models.librarian import Librarian
from app.models.support import LocalContent
from app.sarvam.stt import transcribe_audio
from app.storage.s3 import presign_download
from app.whatomate.client import whatomate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/community", tags=["admin-community"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class ContentResponse(BaseModel):
    id: str
    librarian_id: str
    librarian_name: str | None
    librarian_district: str | None
    content_type: str
    description: str | None
    voice_note_url: str | None
    photo_url: str | None
    status: str
    created_at: datetime


class ContentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ContentResponse]


class StatusUpdateRequest(BaseModel):
    status: str  # reviewed | published | rejected


class TranscribeResponse(BaseModel):
    transcript: str | None
    saved: bool


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _content_to_response(
    c: LocalContent,
    librarian_name: str | None = None,
    librarian_district: str | None = None,
) -> ContentResponse:
    return ContentResponse(
        id=str(c.id),
        librarian_id=str(c.librarian_id),
        librarian_name=librarian_name,
        librarian_district=librarian_district,
        content_type=c.content_type,
        description=c.description,
        voice_note_url=c.voice_note_url,
        photo_url=c.photo_url,
        status=c.status,
        created_at=c.created_at,
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("", response_model=ContentListResponse)
async def list_community_content(
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
    status: str = Query(""),
    content_type: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    allowed_districts = district_filter(admin)

    # Join with Librarian for name/district
    stmt = select(LocalContent, Librarian.name, Librarian.district).join(
        Librarian, LocalContent.librarian_id == Librarian.id, isouter=True
    )

    if status:
        stmt = stmt.where(LocalContent.status == status)
    if content_type:
        stmt = stmt.where(LocalContent.content_type == content_type)
    if allowed_districts is not None:
        stmt = stmt.where(Librarian.district.in_(allowed_districts))

    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(LocalContent.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    return ContentListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_content_to_response(c, name, district) for c, name, district in rows],
    )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_community_content(
    content_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LocalContent, Librarian.name, Librarian.district)
        .join(Librarian, LocalContent.librarian_id == Librarian.id, isouter=True)
        .where(LocalContent.id == content_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(404, "Content not found")
    c, name, district = row
    return _content_to_response(c, name, district)


@router.put("/{content_id}/status", response_model=ContentResponse)
async def update_content_status(
    content_id: UUID,
    body: StatusUpdateRequest,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    if body.status not in ("reviewed", "published", "rejected"):
        raise HTTPException(400, "status must be reviewed | published | rejected")

    result = await db.execute(
        select(LocalContent, Librarian.name, Librarian.district)
        .join(Librarian, LocalContent.librarian_id == Librarian.id, isouter=True)
        .where(LocalContent.id == content_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(404, "Content not found")

    c, name, district = row
    c.status = body.status
    await db.commit()
    await db.refresh(c)
    logger.info("LocalContent %s status → %s by %s", content_id, body.status, admin.email)
    return _content_to_response(c, name, district)


@router.get("/{content_id}/audio")
async def get_audio_url(
    content_id: UUID,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Get a pre-signed S3 URL for the voice note (1 hour TTL)."""
    result = await db.execute(select(LocalContent).where(LocalContent.id == content_id))
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Content not found")
    if not c.voice_note_url:
        raise HTTPException(404, "No voice note for this content")

    try:
        url = presign_download(c.voice_note_url)
    except Exception as e:
        logger.error("S3 presign error for content %s: %s", content_id, e)
        raise HTTPException(500, "Could not generate audio URL")

    return {"url": url, "expires_in": 3600}


@router.post("/{content_id}/transcribe", response_model=TranscribeResponse)
async def transcribe_content_audio(
    content_id: UUID,
    admin: Annotated[AdminUser, Depends(require_role("admin", "super_admin"))],
    db: AsyncSession = Depends(get_db),
):
    """
    Download the voice note from Whatomate/S3 and transcribe it using Sarvam STT.
    If successful, saves transcript as description.
    """
    result = await db.execute(select(LocalContent).where(LocalContent.id == content_id))
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(404, "Content not found")
    if not c.voice_note_url:
        raise HTTPException(400, "No voice note to transcribe")

    try:
        # Download audio bytes from S3 via signed URL
        import httpx
        audio_url = presign_download(c.voice_note_url)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(audio_url)
            resp.raise_for_status()
            audio_bytes = resp.content

        transcript = await transcribe_audio(audio_bytes, mime_type="audio/ogg")
    except Exception as e:
        logger.error("Transcription failed for content %s: %s", content_id, e)
        raise HTTPException(500, f"Transcription failed: {e}")

    saved = False
    if transcript:
        c.description = transcript
        await db.commit()
        saved = True

    return TranscribeResponse(transcript=transcript, saved=saved)
