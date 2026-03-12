"""
Shared FastAPI dependencies for admin routes.

Usage:
    @router.get("/some-route")
    async def handler(admin: AdminUser = Depends(get_current_admin)):
        ...

    # Require a specific role:
    @router.post("/super-only")
    async def handler(admin: AdminUser = Depends(require_role("super_admin"))):
        ...

    # Allow multiple roles:
    @router.get("/admin-or-super")
    async def handler(admin: AdminUser = Depends(require_role("super_admin", "admin"))):
        ...
"""
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.admin import AdminUser

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    """
    Decode the Bearer JWT, verify it is an access token,
    and return the corresponding active AdminUser from DB.
    Raises 401 on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise credentials_exception

    # Must be an access token (not refresh)
    if payload.get("type") != "access":
        raise credentials_exception

    admin_id: str | None = payload.get("sub")
    if not admin_id:
        raise credentials_exception

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin_id, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise credentials_exception

    return admin


def require_role(*roles: str):
    """
    Returns a FastAPI dependency that checks the current admin has one of the given roles.
    Always includes super_admin implicitly (super_admin can do everything).

    Usage:
        Depends(require_role("admin", "district_coordinator"))
    """
    allowed = set(roles) | {"super_admin"}

    async def _check(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{admin.role}' is not permitted for this action",
            )
        return admin

    return _check


def district_filter(admin: AdminUser) -> list[str] | None:
    """
    Returns the list of districts the admin is restricted to,
    or None if they can see all districts (super_admin / admin).
    """
    if admin.role == "district_coordinator":
        return admin.assigned_districts or []
    return None
