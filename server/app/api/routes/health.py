from fastapi import APIRouter

from ...core.config import get_settings
from ...core.database import mongo

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness probe. Reports degraded (but still 200) when MongoDB is down."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "database": "connected" if mongo.connected else "unavailable",
    }
