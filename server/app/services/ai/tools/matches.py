"""AI tools for match evidence.

Returns the persisted match (score, breakdown, reasons, matched/mismatched
fields) and the two sides. The AI explains the engine's result; it never
recomputes scores.
"""

from __future__ import annotations

from bson import ObjectId

from ....repositories import (
    match_repository,
    reconciliation_run_repository,
    transaction_repository,
)
from ..tools import register_tool, require_view

_OBJ_ID_PARAM = {"type": "string", "description": "24-character MongoDB ObjectId"}


@register_tool(
    "get_match",
    description=(
        "Retrieve a persisted match's score, evidence and transaction sides. Use "
        "this to explain why the engine grouped specific records together — the "
        "score and reasons are retrieved, never recomputed."
    ),
    schema={
        "type": "object",
        "properties": {"match_id": _OBJ_ID_PARAM},
        "required": ["match_id"],
        "additionalProperties": False,
    },
)
async def get_match(ctx, args: dict) -> dict:
    """Retrieve a persisted match's score, evidence and transaction sides."""
    require_view(ctx)
    match_id = args.get("match_id") or args.get("id")
    if not match_id:
        return {"error": "match_id is required."}
    try:
        _id = ObjectId(str(match_id))
    except Exception:
        return {"match": {}, "message": "That match id isn't valid."}
    match = await match_repository.get_match_by_id(ctx.db, ctx.workspace_id, _id)
    if match is None:
        return {"match": {}, "message": "That match wasn't found."}
    evidence = match.evidence or {}
    sides = []
    for tid in (match.transaction_ids or []):
        txn = await transaction_repository.get_by_id(ctx.db, ctx.workspace_id, tid)
        sides.append(_txn_light(txn))

    run = None
    try:
        run_obj = await reconciliation_run_repository.get_by_id(
            ctx.db, ctx.workspace_id, match.reconciliation_run_id
        )
        run = {
            "id": str(run_obj.id),
            "status": run_obj.status.value if hasattr(run_obj.status, "value") else str(run_obj.status),
            "totalTransactions": run_obj.total_transactions,
        }
    except Exception:
        run = None

    return {
        "match": {
            "id": str(match.id),
            "reconciliationRunId": str(match.reconciliation_run_id),
            "matchType": match.match_type.value if hasattr(match.match_type, "value") else str(match.match_type),
            "status": match.status,
            "confidence": str(match.confidence) if match.confidence is not None else None,
            "scoreBreakdown": {k: str(v) for k, v in (evidence.get("scoreBreakdown") or {}).items()},
            "reasons": evidence.get("reasons") or [],
            "matchedFields": evidence.get("matchedFields") or [],
            "mismatchedFields": evidence.get("mismatchedFields") or [],
            "tolerancesUsed": evidence.get("tolerancesUsed") or {},
        },
        "transactions": sides,
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
        "direction": txn.direction.value if hasattr(txn.direction, "value") else str(txn.direction),
        "reference": txn.reference,
        "counterparty": txn.counterparty,
        "description": txn.description,
        "transaction_type": txn.transaction_type,
    }