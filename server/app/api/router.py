from fastapi import APIRouter

from .routes import (
    ai,
    audit,
    exceptions,
    files,
    health,
    overview,
    reconciliations,
    sources,
    transactions,
    users,
    workspaces,
)

# Authentication endpoints intentionally live in Next.js (Auth.js).
# FastAPI exposes business APIs only.
api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(
    reconciliations.router, prefix="/reconciliations", tags=["reconciliations"]
)
api_router.include_router(exceptions.router, prefix="/exceptions", tags=["exceptions"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(overview.router, prefix="/overview", tags=["overview"])
