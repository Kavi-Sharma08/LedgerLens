"""Workspace-wide exception feed.

The Exceptions screen lists every open/resolved exception for the workspace,
not per reconciliation run. Run-scoped listings remain available under
/api/reconciliations/{run_id}/exceptions."""
from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_membership, get_current_workspace, require_permission
from ...core.database import get_database
from ...core.errors import AppError, NotFoundError
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


@router.patch("/{exception_id}/assign")
async def assign_exception(
    exception_id: str,
    body: dict,
    membership=Depends(require_permission("resolve_exception")),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Assign an exception to a team member."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    assigned_to = body.get("assignedTo")
    if not assigned_to:
        raise AppError(status_code=422, message="assignedTo is required.")

    try:
        assignee_id = ObjectId(assigned_to)
    except Exception:
        raise AppError(status_code=422, message="Invalid assignedTo user id.")

    result = await exception_repository.assign_exception(db, workspace.id, _id, assignee_id)
    if result is None:
        raise NotFoundError(message="Exception not found.")
    return to_exception_public(result)


@router.patch("/{exception_id}/status")
async def update_exception_status(
    exception_id: str,
    body: dict,
    membership=Depends(require_permission("resolve_exception")),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Change the status of an exception (OPEN -> INVESTIGATING -> RESOLVED/DISMISSED)."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    new_status_str = body.get("status", "")
    try:
        new_status = ExceptionStatus(new_status_str)
    except ValueError:
        raise AppError(
            status_code=422,
            message=f"Invalid status: {new_status_str}. Use OPEN, INVESTIGATING, RESOLVED, or DISMISSED.",
        )

    result = await exception_repository.update_status(
        db, workspace.id, _id, new_status, membership.user_id
    )
    if result is None:
        raise NotFoundError(message="Exception not found.")
    return to_exception_public(result)


@router.post("/{exception_id}/notes")
async def add_exception_note(
    exception_id: str,
    body: dict,
    membership=Depends(require_permission("resolve_exception")),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Add an investigation note to an exception."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    text = body.get("text", "").strip()
    if not text:
        raise AppError(status_code=422, message="Note text is required.")

    result = await exception_repository.add_note(
        db, workspace.id, _id, membership.user_id, text
    )
    if result is None:
        raise NotFoundError(message="Exception not found.")
    return to_exception_public(result)
