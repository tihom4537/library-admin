"""
File upload pre-signing endpoint.
Frontend requests a pre-signed S3 URL, uploads directly to S3 — no file bytes through backend.

POST /admin/upload/presign   → {upload_url, object_key, expires_in}
GET  /admin/upload/view      → 302 redirect to pre-signed GET URL
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.admin.deps import get_current_admin
from app.models.admin import AdminUser
from app.storage import s3

router = APIRouter(prefix="/upload", tags=["admin-upload"])

ALLOWED_FOLDERS = {
    "activity-images",
    "learning",
    "community",
    "reports",
}

ALLOWED_CONTENT_TYPES = s3.ALLOWED_IMAGE_TYPES | s3.ALLOWED_AUDIO_TYPES


class PresignRequest(BaseModel):
    folder: str       # e.g. "activity-images/template_123"
    filename: str     # original filename (used only for extension)
    content_type: str


class PresignResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


@router.post("/presign", response_model=PresignResponse)
async def presign_upload(
    body: PresignRequest,
    admin: Annotated[AdminUser, Depends(get_current_admin)],
):
    # Validate folder prefix
    top_folder = body.folder.split("/")[0]
    if top_folder not in ALLOWED_FOLDERS:
        raise HTTPException(status_code=400, detail=f"Invalid folder '{top_folder}'")

    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Content type '{body.content_type}' not allowed")

    result = s3.presign_upload(body.folder, body.filename, body.content_type)
    return PresignResponse(**result)


@router.get("/view")
async def view_file(
    key: str = Query(..., description="S3 object key"),
    admin: AdminUser = Depends(get_current_admin),
):
    """Redirect to a short-lived pre-signed GET URL for in-browser preview/playback."""
    try:
        url = s3.presign_download(key)
        return RedirectResponse(url=url, status_code=302)
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")
