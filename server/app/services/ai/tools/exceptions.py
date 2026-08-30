"""AI tools for exception evidence.

Returns the exception plus its linked transactions/reconciliation run. Notes
are only surfaced when the member holds the manage_exceptions capability,
mirroring how sensitive notes are exposed elsewhere.
"""

from __future__ import annotations

from bson import ObjectId

from ....repositories import (
    exception_repository,
    reconciliation_run_repository,
    transaction_repository,
)
from ..tools import register_tool, require_view

_OBJ_ID_PARAM = {"type": "string", "description": "24-character MongoDB ObjectId"}


@register_tool(
    "get_exception",
    description=(
        "Retrieve one exception's details (reason code, engine detail, status) and "
        "its linked transaction ids."
    ),
    schema={
        "type": "object",
        "properties": {"exception_id": _OBJ_ID_PARAM},
        "required": ["exception_id"],
        "additionalProperties": False,
    },
)
async def get_exception(ctx, args: dict) -> dict:
    """Retrieve one exception's details and its linked transaction summary."""
    require_view(ctx)
    exc_id = args.get("exception_id") or args.get("id")
    if not exc_id:
        return {"error": "exception_id is required."}
    try:
        _id = ObjectId(str(exc_id))
    except Exception:
        return {"exception": {}, "message": "That exception id isn't valid."}
    exc = await exception_repository.get_by_id(ctx.db, ctx.workspace_id, _id)
    if exc is None:
        return {"exception": {}, "message": "That exception wasn't found."}
    return {
        "exception": {
            "id": str(exc.id),
            "reconciliationRunId": str(exc.reconciliation_run_id),
            "transactionIds": [str(t) for t in (exc.transaction_ids or [])],
            "reasonCode": exc.reason_code.value if hasattr(exc.reason_code, "value") else str(exc.reason_code),
            "detail": exc.detail,
            "status": exc.status.value if hasattr(exc.status, "value") else str(exc.status),
        }
    }


@register_tool(
    "get_exception_notes",
    description=(
        "Retrieve investigation notes on an exception. Only visible to members who "
        "can manage exceptions."
    ),
    schema={
        "type": "object",
        "properties": {"exception_id": _OBJ_ID_PARAM},
        "required": ["exception_id"],
        "additionalProperties": False,
    },
)
async def get_exception_notes(ctx, args: dict) -> dict:
    """Retrieve investigation notes on an exception (permission-gated)."""
    require_view(ctx)
    if not ctx.can_manage_exceptions:
        return {
            "notes": [],
            "message": "Notes are only visible to members who can manage exceptions.",
        }
    exc_id = args.get("exception_id") or args.get("id")
    if not exc_id:
        return {"error": "exception_id is required."}
    try:
        _id = ObjectId(str(exc_id))
    except Exception:
        return {"notes": [], "message": "That exception id isn't valid."}
    exc = await exception_repository.get_by_id(ctx.db, ctx.workspace_id, _id)
    if exc is None:
        return {"notes": [], "message": "That exception wasn't found."}
    notes = []
    for note in (exc.notes or []):
        notes.append(
            {
                "text": note.get("text", ""),
                "createdAt": note.get("createdAt"),
                "userRef": str(note.get("userId", ""))[-6:],
            }
        )
    return {"notes": notes}


@register_tool(
    "get_exception_context",
    description=(
        "Combine one exception with its linked transactions and reconciliation run "
        "for analysis. Use this to explain an exception (what happened, the cause, "
        "the impact, what to review)."
    ),
    schema={
        "type": "object",
        "properties": {"exception_id": _OBJ_ID_PARAM},
        "required": ["exception_id"],
        "additionalProperties": False,
    },
)
async def get_exception_context(ctx, args: dict) -> dict:
    """Combine an exception with its linked transactions and run for analysis."""
    require_view(ctx)
    exc_id = args.get("exception_id") or args.get("id")
    if not exc_id:
        return {"error": "exception_id is required."}
    try:
        _id = ObjectId(str(exc_id))
    except Exception:
        return {"exception": {}, "message": "That exception id isn't valid."}
    exc = await exception_repository.get_by_id(ctx.db, ctx.workspace_id, _id)
    if exc is None:
        return {"exception": {}, "message": "That exception wasn't found."}
    txns = []
    for tid in (exc.transaction_ids or []):
        try:
            txn = await transaction_repository.get_by_id(ctx.db, ctx.workspace_id, ObjectId(str(tid)))
            txns.append(_txn_light(txn))
        except Exception:
            continue
    run = None
    try:
        run_obj = await reconciliation_run_repository.get_by_id(
            ctx.db, ctx.workspace_id, exc.reconciliation_run_id
        )
        run = {
            "id": str(run_obj.id),
            "status": run_obj.status.value if hasattr(run_obj.status, "value") else str(run_obj.status),
            "totalTransactions": run_obj.total_transactions,
            "unmatchedCount": run_obj.unmatched_count,
            "exceptionCount": run_obj.exception_count,
        }
    except Exception:
        run = None
    return {
        "exception": {
            "id": str(exc.id),
            "reasonCode": exc.reason_code.value if hasattr(exc.reason_code, "value") else str(exc.reason_code),
            "detail": exc.detail,
            "status": exc.status.value if hasattr(exc.status, "value") else str(exc.status),
        },
        "transactions": txns,
        "run": run,
    }


def _txn_light(txn) -> dict:
    if txn is None:
        return {}
    return {
        "id": str(txn.id),
        "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
        "amount": str(txn.amount) if txn.amount is not None else None,
        "currency": txn.currency,
        "reference": txn.reference,
        "counterparty": txn.counterparty,
        "status": txn.status,
    }
