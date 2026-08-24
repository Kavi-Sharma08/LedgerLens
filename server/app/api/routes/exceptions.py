"""Workspace-wide exception feed.

The Exceptions screen lists every open/resolved exception for the workspace,
not per reconciliation run. Run-scoped listings remain available under
/api/reconciliations/{run_id}/exceptions."""
from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_workspace
from ...core.database import get_database
from ...core.errors import AppError
from ...models.enums import ExceptionStatus
from ...models.workspace import Workspace
from ...repositories import exception_repository
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...schemas.common import paginated
from ...services.mappers import to_exception_public

router = APIRouter()


@router.get("")
async def list_workspace_exceptions(
    status: ExceptionStatus | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    try:
        page = await exception_repository.list_for_workspace(
            db, workspace.id, status=status, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_exception_public(e) for e in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )
