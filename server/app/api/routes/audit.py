"""Workspace audit log — immutable history of important actions."""
from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_workspace, require_permission
from ...core.database import get_database
from ...core.errors import AppError
from ...models.workspace import Workspace
from ...repositories import audit_repository
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...schemas.common import paginated

router = APIRouter()


@router.get("")
async def list_audit_logs(
    action: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    _=Depends(require_permission("view_audit")),
    db=Depends(get_database),
):
    """Workspace audit feed. Requires ADMIN+ role."""
    try:
        page = await audit_repository.list_for_workspace(
            db, workspace.id, action=action, user_id=user_id, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")

    items = [
        {
            "id": str(entry.id),
            "workspaceId": str(entry.workspace_id),
            "userId": str(entry.user_id),
            "action": entry.action,
            "entityType": entry.entity_type,
            "entityId": entry.entity_id,
            "details": entry.details or {},
            "createdAt": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in page.items
    ]
    return paginated(items, limit or DEFAULT_PAGE_SIZE, page.next_cursor)
