"""
Admin portal API — all routes under /admin prefix.
"""
from fastapi import APIRouter

from app.admin.auth.router import router as auth_router
from app.admin.librarians.router import router as librarians_router
from app.admin.upload.router import router as upload_router
from app.admin.activities.router import router as activities_router
from app.admin.circulars.router import router as circulars_router
from app.admin.dashboard.router import router as dashboard_router
from app.admin.nudges.router import router as nudges_router
from app.admin.community.router import router as community_router
from app.admin.learning.router import router as learning_router
from app.admin.export.router import router as export_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(auth_router)
admin_router.include_router(librarians_router)
admin_router.include_router(upload_router)
admin_router.include_router(activities_router)
admin_router.include_router(circulars_router)
admin_router.include_router(dashboard_router)
admin_router.include_router(nudges_router)
admin_router.include_router(community_router)
admin_router.include_router(learning_router)
admin_router.include_router(export_router)
