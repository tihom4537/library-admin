"""
AWS S3 client for Arivu media uploads.

Upload flow (admin portal):
  1. Frontend calls POST /admin/upload/presign → gets a pre-signed PUT URL + final object key
  2. Frontend uploads file bytes directly to S3 (no data passes through backend)
  3. Frontend stores the returned object_key alongside the record it's creating

Download flow:
  - For admin portal previews: GET /admin/upload/view?key=... → 302 redirect to pre-signed GET URL
  - For WhatsApp (community audio, report photos): use the pre-signed GET URL directly

S3 folder structure:
  activity-images/{template_id}/{filename}
  learning/{module_id}/{step}/{filename}
  community/{content_id}/{filename}
  reports/{report_id}/{filename}
"""
import logging
import mimetypes
import uuid

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Allowed MIME types per folder
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/ogg", "audio/wav", "audio/mp4", "audio/aac"}

# Pre-signed URL expiry
UPLOAD_URL_TTL = 300      # 5 minutes to complete the upload
DOWNLOAD_URL_TTL = 3600   # 1 hour for viewing/playback


def _client():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def presign_upload(
    folder: str,
    filename: str,
    content_type: str,
) -> dict:
    """
    Generate a pre-signed S3 PUT URL.
    Returns {"upload_url": str, "object_key": str, "expires_in": int}
    """
    ext = _safe_extension(filename, content_type)
    object_key = f"{folder.strip('/')}/{uuid.uuid4().hex}{ext}"

    try:
        url = _client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.aws_s3_bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=UPLOAD_URL_TTL,
        )
        return {"upload_url": url, "object_key": object_key, "expires_in": UPLOAD_URL_TTL}
    except ClientError as e:
        logger.error("S3 presign upload error: %s", e)
        raise


def presign_download(object_key: str, ttl: int = DOWNLOAD_URL_TTL) -> str:
    """
    Generate a pre-signed S3 GET URL for viewing/playback.
    """
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.aws_s3_bucket, "Key": object_key},
            ExpiresIn=ttl,
        )
    except ClientError as e:
        logger.error("S3 presign download error: %s key=%s", e, object_key)
        raise


def delete_object(object_key: str) -> None:
    """Delete a single S3 object (e.g., when admin rejects content)."""
    try:
        _client().delete_object(Bucket=settings.aws_s3_bucket, Key=object_key)
    except ClientError as e:
        logger.warning("S3 delete error (non-fatal): %s key=%s", e, object_key)


def _safe_extension(filename: str, content_type: str) -> str:
    """Derive a safe file extension from content-type, fallback to original extension."""
    ext = mimetypes.guess_extension(content_type)
    if ext and ext not in (".jpe",):  # .jpe is a weird mimetypes alias for jpeg
        return ext
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()[:5]
    return ""
