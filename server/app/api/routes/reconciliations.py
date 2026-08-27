from fastapi import APIRouter, Depends, Query

from ...api.deps import get_current_membership, get_current_user, get_current_workspace, require_permission
from ...core.database import get_database
from ...core.errors import AppError, NotFoundError
from ...models.enums import ExceptionStatus, ReconciliationStatus, WorkspaceRole
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import exception_repository, match_repository, reconciliation_run_repository
from ...repositories.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursorError
from ...schemas.common import paginated
from ...schemas.reconciliation import RunCreate
from ...services.audit_helper import log_audit
from ...services.mappers import to_exception_public, to_match_public, to_run_public
from ...services.reconciliation_service import start_run

router = APIRouter()


@router.post("", status_code=201)
async def create_reconciliation_run(
    payload: RunCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Run a deterministic reconciliation across the given sources.

    The run record stores the algorithm version and the exact configuration
    used, so results remain reproducible and auditable."""
    from bson import ObjectId

    source_ids = []
    for raw in payload.sourceIds:
        try:
            source_ids.append(ObjectId(raw))
        except Exception as exc:
            raise AppError(status_code=422, message="One of the source ids isn't valid.") from exc

    run = await start_run(db, workspace.id, source_ids=source_ids)

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="reconciliation_started",
        entity_type="reconciliation_run",
        entity_id=str(run.id),
        details={"sourceCount": len(source_ids), "sourceIds": [str(s) for s in source_ids]},
    )

    return to_run_public(run)


@router.get("")
async def list_reconciliation_runs(
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    try:
        page = await reconciliation_run_repository.list_runs(
            db, workspace.id, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_run_public(r) for r in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{run_id}")
async def get_reconciliation_run(
    run_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    run = await reconciliation_run_repository.get_by_id(db, workspace.id, run_id)
    return to_run_public(run)


@router.get("/{run_id}/matches")
async def list_run_matches(
    run_id: str,
    status: list[ReconciliationStatus] | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    from ...repositories import match_repository
    from bson import ObjectId

    try:
        _id = ObjectId(run_id)
    except Exception as exc:
        raise AppError(status_code=404, message="That reconciliation run doesn't exist.") from exc

    # Workspace-scoped existence check first (foreign ids -> 404).
    await reconciliation_run_repository.get_by_id(db, workspace.id, _id)

    try:
        page = await match_repository.list_matches_for_run(
            db, workspace.id, _id,
            statuses=[s.value for s in status] if status else None,
            limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_match_public(m) for m in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{run_id}/unmatched")
async def list_run_unmatched(
    run_id: str,
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Transactions from this run's source scope that ended without a match."""
    from ...services.reconciliation_service import list_run_unmatched

    try:
        page = await list_run_unmatched(
            db, workspace.id, run_id, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        page.items,
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.get("/{run_id}/exceptions")
async def list_run_exceptions(
    run_id: str,
    status: ExceptionStatus | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    from bson import ObjectId

    try:
        _id = ObjectId(run_id)
    except Exception as exc:
        raise AppError(status_code=404, message="That reconciliation run doesn't exist.") from exc

    await reconciliation_run_repository.get_by_id(db, workspace.id, _id)

    try:
        page = await exception_repository.list_for_run(
            db, workspace.id, _id, status=status, limit=limit, cursor=cursor
        )
    except InvalidCursorError:
        raise AppError(status_code=400, message="Pagination cursor is invalid.")
    return paginated(
        [to_exception_public(e) for e in page.items],
        limit or DEFAULT_PAGE_SIZE,
        page.next_cursor,
    )


@router.post("/{run_id}/matches/{match_id}/approve")
async def approve_match(
    run_id: str,
    match_id: str,
    body: dict | None = None,
    membership=Depends(require_permission("approve_match")),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Approve a match (human confirms the engine's suggestion)."""
    from bson import ObjectId

    try:
        _match_id = ObjectId(match_id)
    except Exception:
        raise AppError(status_code=404, message="Match not found.")

    match = await match_repository.get_match_by_id(db, workspace.id, _match_id)
    if match is None:
        raise NotFoundError(message="Match not found.")

    note = (body or {}).get("note", "")
    updated = await match_repository.approve_match(
        db, workspace.id, _match_id, membership.user_id, note
    )

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=membership.user_id,
        action="match_approved",
        entity_type="match",
        entity_id=match_id,
        details={"reconciliationRunId": run_id, "note": note or ""},
    )

    return to_match_public(updated)


@router.post("/{run_id}/matches/{match_id}/reject")
async def reject_match(
    run_id: str,
    match_id: str,
    body: dict | None = None,
    membership=Depends(require_permission("approve_match")),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
):
    """Reject a match (human disagrees with the engine's suggestion)."""
    from bson import ObjectId

    try:
        _match_id = ObjectId(match_id)
    except Exception:
        raise AppError(status_code=404, message="Match not found.")

    match = await match_repository.get_match_by_id(db, workspace.id, _match_id)
    if match is None:
        raise NotFoundError(message="Match not found.")

    note = (body or {}).get("note", "")
    updated = await match_repository.reject_match(
        db, workspace.id, _match_id, membership.user_id, note
    )

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=membership.user_id,
        action="match_rejected",
        entity_type="match",
        entity_id=match_id,
        details={"reconciliationRunId": run_id, "note": note or ""},
    )

    return to_match_public(updated)
