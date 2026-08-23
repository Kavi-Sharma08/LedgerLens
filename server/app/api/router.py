from fastapi import APIRouter

from .routes import health, users, workspaces

# Authentication endpoints intentionally live in Next.js (Auth.js).
# FastAPI exposes business APIs only.
api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
