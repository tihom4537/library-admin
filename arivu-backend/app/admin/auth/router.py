"""
Admin authentication endpoints.

POST /admin/auth/login    — email + password → access_token + refresh_token
POST /admin/auth/refresh  — refresh_token → new access_token
GET  /admin/auth/me       — current admin profile
POST /admin/auth/create-first-admin  — one-time bootstrap (only works if 0 admins exist)
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import get_current_admin
from app.config import settings
from app.db.database import get_db
from app.models.admin import AdminUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["admin-auth"])

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    name: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminMeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    assigned_districts: list[str] | None
    last_login_at: datetime | None

    class Config:
        from_attributes = True


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "super_admin"


# ─── Token helpers ────────────────────────────────────────────────────────────

def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "type": token_type, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _make_token_pair(admin_id: str) -> tuple[str, str]:
    access = _create_token(
        admin_id,
        "access",
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh = _create_token(
        admin_id,
        "refresh",
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    return access, refresh


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == body.email, AdminUser.is_active == True)
    )
    admin = result.scalar_one_or_none()

    if admin is None or not _pwd_context.verify(body.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Update last login timestamp
    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access, refresh = _make_token_pair(str(admin.id))
    logger.info("Admin login: %s (%s)", admin.email, admin.role)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        role=admin.role,
        name=admin.name,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from jose import JWTError

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "refresh":
        raise credentials_exception

    admin_id = payload.get("sub")
    if not admin_id:
        raise credentials_exception

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin_id, AdminUser.is_active == True)
    )
    if result.scalar_one_or_none() is None:
        raise credentials_exception

    access = _create_token(
        admin_id,
        "access",
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return AccessTokenResponse(access_token=access)


@router.get("/me", response_model=AdminMeResponse)
async def me(admin: AdminUser = Depends(get_current_admin)):
    return AdminMeResponse(
        id=str(admin.id),
        email=admin.email,
        name=admin.name,
        role=admin.role,
        assigned_districts=admin.assigned_districts,
        last_login_at=admin.last_login_at,
    )


@router.post("/create-first-admin", response_model=AdminMeResponse, status_code=201)
async def create_first_admin(body: CreateAdminRequest, db: AsyncSession = Depends(get_db)):
    """
    Bootstrap endpoint — creates the first admin account.
    Only works when the admin_user table is empty.
    Disable or remove this endpoint after initial setup.
    """
    count_result = await db.execute(select(func.count()).select_from(AdminUser))
    count = count_result.scalar()
    if count and count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts already exist. Use the admin portal to create more.",
        )

    if body.role not in ("super_admin", "admin", "district_coordinator"):
        raise HTTPException(status_code=400, detail="Invalid role")

    admin = AdminUser(
        email=body.email,
        password_hash=_pwd_context.hash(body.password),
        name=body.name,
        role=body.role,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    logger.info("First admin created: %s (%s)", admin.email, admin.role)

    return AdminMeResponse(
        id=str(admin.id),
        email=admin.email,
        name=admin.name,
        role=admin.role,
        assigned_districts=admin.assigned_districts,
        last_login_at=admin.last_login_at,
    )
