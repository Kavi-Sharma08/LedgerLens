"""AI Reconciliation Intelligence routes.

Every endpoint:
  - authenticates the user (get_current_user)
  - resolves the active workspace and verifies membership (get_current_workspace)
  - requires at least the same view permission as the underlying data
  - verifies the referenced entity exists in the CURRENT workspace (so a forged
    foreign id behaves as not-found, never a cross-workspace leak) — except for
    /ask which has no entity path
  - invokes the AI service (which internally re-checks capability flags)
  - logs the AI activity to the audit record (no secrets, no prompts)
"""

import logging

from fastapi import APIRouter, Depends
from bson import ObjectId

from ...api.deps import (
    get_current_membership,
    get_current_user,
    get_current_workspace,
    require_permission,
)
from ...core.database import get_database
from ...core.errors import (
    AppError,
    NotFoundError,
    TransactionNotFoundError,
)
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import (
    exception_repository,
    match_repository,
    reconciliation_run_repository,
    transaction_repository,
)
from ...services.audit_helper import log_audit
from ...services.ai.ai_service import (
    AIAnalysisError,
    analyze_exception,
    analyze_match,
    analyze_reconciliation,
    analyze_transaction,
    ask,
    resolve_capabilities,
)
from ...services.ai.schemas import AskRequest

logger = logging.getLogger("ledgerlens.ai.routes")

router = APIRouter()

# Map an AI error category to a stable, non-sensitive code and HTTP status that
# the frontend can present as a specific message. Never exposes internals.
_AI_CATEGORY_CODES = {
    "rate_limited": ("rate_limited", 429),
    "ai_unavailable": ("ai_unavailable", 503),
    "ai_request_failed": ("ai_request_failed", 502),
    "tool_execution_failed": ("tool_execution_failed", 502),
    "no_answer": ("no_answer", 502),
}



def _category_from(exc) -> str:
    return getattr(exc, "category", "ai_request_failed")


async def _run_with_audit(
    db,
    *,
    user_id,
    workspace,
    membership,
    action: str,
    entity_type: str,
    entity_id: str,
    entity_kwargs: dict,
    coroutine,
):
    """Run the AI coroutine and record the activity afterwards."""
    can_view, can_manage = resolve_capabilities(
        db, workspace.id, user_id, membership.role, workspace.role_permissions
    )
    if not can_view:
        raise PermissionError("view_data")
    try:
        result = await coroutine(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
            can_view=can_view,
            can_manage_exceptions=can_manage,
            **entity_kwargs,
        )
    except AIAnalysisError as exc:
        code, status = _AI_CATEGORY_CODES.get(
            _category_from(exc), ("ai_request_failed", 502)
        )
        await log_audit(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
            action=f"{action}_failed",
            entity_type=entity_type,
            entity_id=entity_id,
            details={"reason": _safe_reason(str(exc)), "category": _category_from(exc)},
        )
        raise AppError(status_code=status, message=str(exc), code=code) from exc
    except PermissionError as exc:
        raise AppError(status_code=403, message="You don't have permission to do this.") from exc

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details={},  # minimal, secret-free audit record
    )
    return result


def _safe_reason(message: str) -> str:
    # Keep only a short, user-safe first sentence for the audit trail.
    return (message or "AI analysis failed")[:200]


@router.post("/transaction/{transaction_id}/analyze")
async def ai_transaction_analyze(
    transaction_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    membership=Depends(get_current_membership),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    from bson import ObjectId as OID

    try:
        txn_id = OID(transaction_id)
    except Exception:
        raise TransactionNotFoundError()
    if await transaction_repository.get_by_id(db, workspace.id, txn_id) is None:
        raise TransactionNotFoundError()
    return await _run_with_audit(
        db,
        user_id=current_user.id,
        workspace=workspace,
        membership=membership,
        action="ai_transaction_analyzed",
        entity_type="transaction",
        entity_id=str(txn_id),
        coroutine=analyze_transaction,
        entity_kwargs={"transaction_id": str(txn_id)},
    )


@router.post("/match/{match_id}/analyze")
async def ai_match_analyze(
    match_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    membership=Depends(get_current_membership),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    try:
        _id = ObjectId(match_id)
    except Exception:
        raise NotFoundError(message="Match not found.")
    if await match_repository.get_match_by_id(db, workspace.id, _id) is None:
        raise NotFoundError(message="Match not found.")
    return await _run_with_audit(
        db,
        user_id=current_user.id,
        workspace=workspace,
        membership=membership,
        action="ai_match_analyzed",
        entity_type="match",
        entity_id=str(_id),
        coroutine=analyze_match,
        entity_kwargs={"match_id": str(_id)},
    )


@router.post("/exception/{exception_id}/analyze")
async def ai_exception_analyze(
    exception_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    membership=Depends(get_current_membership),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    try:
        _id = ObjectId(exception_id)
    except Exception:
        raise NotFoundError(message="Exception not found.")
    if await exception_repository.get_by_id(db, workspace.id, _id) is None:
        raise NotFoundError(message="Exception not found.")
    return await _run_with_audit(
        db,
        user_id=current_user.id,
        workspace=workspace,
        membership=membership,
        action="ai_exception_analyzed",
        entity_type="exception",
        entity_id=str(_id),
        coroutine=analyze_exception,
        entity_kwargs={"exception_id": str(_id)},
    )


@router.post("/reconciliation/{run_id}/analyze")
async def ai_reconciliation_analyze(
    run_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    membership=Depends(get_current_membership),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    try:
        run = await reconciliation_run_repository.get_by_id(db, workspace.id, run_id)
    except Exception:
        raise NotFoundError(message="That reconciliation run doesn't exist.")
    return await _run_with_audit(
        db,
        user_id=current_user.id,
        workspace=workspace,
        membership=membership,
        action="ai_reconciliation_analyzed",
        entity_type="reconciliation_run",
        entity_id=str(run.id),
        coroutine=analyze_reconciliation,
        entity_kwargs={"run_id": str(run.id)},
    )


@router.post("/ask")
async def ai_ask(
    payload: AskRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    membership=Depends(get_current_membership),
    db=Depends(get_database),
    __=Depends(require_permission("view_data")),
):
    """Controlled 'Ask LedgerLens' question answering within this workspace.

    If the question binds a specific transaction/run/exception id, that entity
    is resolved against the current workspace first (authorization identical to
    the dedicated analyze endpoints) so a foreign id cannot be used to reach
    another workspace's data via the chat path.
    """
    if payload.transaction_id:
        try:
            tid = ObjectId(payload.transaction_id)
        except Exception:
            raise TransactionNotFoundError()
        if await transaction_repository.get_by_id(db, workspace.id, tid) is None:
            raise TransactionNotFoundError()
    if payload.reconciliation_run_id:
        try:
            await reconciliation_run_repository.get_by_id(db, workspace.id, payload.reconciliation_run_id)
        except Exception:
            raise NotFoundError(message="That reconciliation run doesn't exist.")
    if payload.exception_id:
        try:
            eid = ObjectId(payload.exception_id)
        except Exception:
            raise NotFoundError(message="Exception not found.")
        if await exception_repository.get_by_id(db, workspace.id, eid) is None:
            raise NotFoundError(message="Exception not found.")
    if payload.match_id:
        try:
            mid = ObjectId(payload.match_id)
        except Exception:
            raise NotFoundError(message="Match not found.")
        if await match_repository.get_match_by_id(db, workspace.id, mid) is None:
            raise NotFoundError(message="Match not found.")

    can_view, can_manage = resolve_capabilities(
        db, workspace.id, current_user.id, membership.role, workspace.role_permissions
    )
    if not can_view:
        raise AppError(status_code=403, message="You don't have permission to do this.")
    try:
        result = await ask(
            db,
            workspace_id=workspace.id,
            user_id=current_user.id,
            request=payload,
            can_view=can_view,
            can_manage_exceptions=can_manage,
        )
    except AIAnalysisError as exc:
        code, status = _AI_CATEGORY_CODES.get(
            _category_from(exc), ("ai_request_failed", 502)
        )
        await log_audit(
            db,
            workspace_id=workspace.id,
            user_id=current_user.id,
            action="ai_ask_failed",
            details={"reason": _safe_reason(str(exc)), "category": _category_from(exc)},
        )
        raise AppError(status_code=status, message=str(exc), code=code) from exc

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="ai_ask",
        details={"questionPreview": payload.question[:160]},
    )
    return result
