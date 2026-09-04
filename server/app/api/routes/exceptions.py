"""Workspace-wide exception feed.

The Exceptions screen lists every open/resolved exception for the workspace,
not per reconciliation run. Run-scoped listings remain available under
/api/reconciliations/{run_id}/exceptions."""
from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_user, get_current_workspace, require_permission
from ...core.database import get_database
from ...core.errors import AppError, NotFoundError
from ...models.enums import ExceptionStatus
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import exception_repository
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...schemas.common import paginated
from ...schemas.reconciliation import NotePublic
from ...services.audit_helper import log_audit
from ...services.mappers import to_exception_public, to_note_public

router = APIRouter()


@router.get("")
async def list_workspace_exceptions(
    status: ExceptionStatus | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
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
    membership=Depends(require_permission("manage_exceptions")),
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

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=membership.user_id,
        action="exception_assigned",
        entity_type="exception",
        entity_id=exception_id,
        details={"assignedTo": assigned_to},
    )

    return to_exception_public(result)


@router.patch("/{exception_id}/status")
async def update_exception_status(
    exception_id: str,
    body: dict,
    membership=Depends(require_permission("manage_exceptions")),
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

    result = await exception_repository.get_by_id(db, workspace.id, _id)
    if result is None:
        raise NotFoundError(message="Exception not found.")

    old_status = result.status.value if hasattr(result.status, 'value') else str(result.status)

    result = await exception_repository.update_status(
        db, workspace.id, _id, new_status, membership.user_id
    )

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=membership.user_id,
        action="exception_status_changed",
        entity_type="exception",
        entity_id=exception_id,
        details={
            "oldStatus": old_status,
            "newStatus": new_status.value,
        },
    )

    return to_exception_public(result)


@router.post("/{exception_id}/notes")
async def add_exception_note(
    exception_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    _=Depends(require_permission("view_data")),
    db=Depends(get_database),
):
    """Add an investigation note to an exception.

    Any active member who can view the workspace's data may add notes; the
    exception must belong to the authenticated workspace."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    text = body.get("text", "").strip()
    if not text:
        raise AppError(status_code=422, message="Note text is required.")
    if len(text) > 2000:
        raise AppError(status_code=422, message="Note is too long. Keep it under 2000 characters.")

    note = await exception_repository.add_note(
        db, workspace.id, _id, current_user.id, text, created_by=current_user.name
    )
    if note is None:
        raise NotFoundError(message="Exception not found.")

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="exception_note_added",
        entity_type="exception",
        entity_id=exception_id,
        details={"noteId": note["id"], "notePreview": text[:200]},
    )

    return to_note_public(note)


@router.patch("/{exception_id}/notes/{note_id}")
async def update_exception_note(
    exception_id: str,
    note_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    _=Depends(require_permission("view_data")),
    db=Depends(get_database),
):
    """Edit an investigation note's content."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    if not note_id:
        raise AppError(status_code=404, message="Note not found.")

    text = body.get("text", "").strip()
    if not text:
        raise AppError(status_code=422, message="Note text is required.")
    if len(text) > 2000:
        raise AppError(status_code=422, message="Note is too long. Keep it under 2000 characters.")

    note = await exception_repository.update_note(db, workspace.id, _id, note_id, text)
    if note is None:
        raise NotFoundError(message="Note not found.")

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="exception_note_updated",
        entity_type="exception",
        entity_id=exception_id,
        details={"noteId": note_id},
    )

    return to_note_public(note)


@router.delete("/{exception_id}/notes/{note_id}")
async def delete_exception_note(
    exception_id: str,
    note_id: str,
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    _=Depends(require_permission("view_data")),
    db=Depends(get_database),
):
    """Delete an investigation note from an exception."""
    from bson import ObjectId

    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise AppError(status_code=404, message="Exception not found.")

    if not note_id:
        raise AppError(status_code=404, message="Note not found.")

    note = await exception_repository.delete_note(db, workspace.id, _id, note_id)
    if note is None:
        raise NotFoundError(message="Note not found.")

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="exception_note_deleted",
        entity_type="exception",
        entity_id=exception_id,
        details={"noteId": note_id},
    )

    return {"id": note_id}
