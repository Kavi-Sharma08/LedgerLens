"""AI tools for reconciliation-run evidence.

Reads the persisted run (the engine remains authoritative) plus candidate
pairs for a transaction within a run, mapping rejected/candidate outcomes so
the AI can explain WHY a transaction was or wasn't matched without recomputing
any matching logic.

Counts semantics (explained to the LLM via `countsNote`):
  - totalTransactions = number of records the engine COMPARED in the run's
    scope (both sides combined). It is not "partially processed".
  - matched / likely / ambiguous / unmatched are DECISION counts, not
    transaction-record counts: one match groups at least two records.
  - unmatchedCount counts A-side records that received no match decision;
    B-side leftovers are persisted as NEEDS_REVIEW exceptions.
  - resolution progress is not `matchedCount / totalTransactions`.
"""

from __future__ import annotations

from bson import ObjectId

from ....models.enums import ReconciliationStatus
from ....repositories import (
    exception_repository,
    match_repository,
    reconciliation_run_repository,
    transaction_repository,
)
from ..tools import register_tool, require_view

_OBJ_ID_PARAM = {"type": "string", "description": "24-character MongoDB ObjectId"}

COUNTS_NOTE = (
    "totalTransactions is the number of records compared in this run's scope, "
    "not a partial-processing figure. matchedCount/likelyMatchCount/ambiguousCount "
    "are decision (group) counts — a match groups two or more records. "
    "unmatchedCount counts A-side records that ended with no match decision; "
    "B-side leftovers appear as NEEDS_REVIEW exceptions. Do not describe "
    "matchedCount as a fraction of totalTransactions: they measure different things."
)


def _run_summary(run) -> dict:
    return {
        "id": str(run.id),
        "status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "totalTransactions": run.total_transactions,
        "matchedCount": run.matched_count,
        "likelyMatchCount": run.likely_match_count,
        "ambiguousCount": run.ambiguous_count,
        "unmatchedCount": run.unmatched_count,
        "exceptionCount": run.exception_count,
        "algorithmVersion": run.algorithm_version,
        "countsNote": COUNTS_NOTE,
    }


@register_tool(
    "get_reconciliation_run",
    description=(
        "Retrieve one reconciliation run's status, scope and counts. Use this when "
        "the question targets a specific run and you already know its id."
    ),
    schema={
        "type": "object",
        "properties": {
            "reconciliation_run_id": _OBJ_ID_PARAM,
            "run_id": _OBJ_ID_PARAM,
        },
        "required": ["reconciliation_run_id"],
        "additionalProperties": False,
    },
)
async def get_reconciliation_run(ctx, args: dict) -> dict:
    """Retrieve a reconciliation run's status, scope and counts."""
    require_view(ctx)
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not run_id:
        return {"error": "reconciliation_run_id is required."}
    try:
        run = await reconciliation_run_repository.get_by_id(
            ctx.db, ctx.workspace_id, run_id
        )
    except Exception:
        return {"run": {}, "message": "That reconciliation run wasn't found."}
    scope = run.transaction_scope or {}
    return {
        "run": {
            **_run_summary(run),
            "sourceIds": [str(s) for s in (run.source_ids or [])],
            "dateFrom": _iso(scope.get("dateFrom")),
            "dateTo": _iso(scope.get("dateTo")),
            "startedAt": _iso(run.started_at),
            "completedAt": _iso(run.completed_at),
            "error": run.error,
        }
    }


@register_tool(
    "get_reconciliation_summary",
    description=(
        "High-level summary of a reconciliation run's outcome (counts + status). "
        "Prefer over get_reconciliation_run when you only need the outcome numbers."
    ),
    schema={
        "type": "object",
        "properties": {
            "reconciliation_run_id": _OBJ_ID_PARAM,
            "run_id": _OBJ_ID_PARAM,
        },
        "required": ["reconciliation_run_id"],
        "additionalProperties": False,
    },
)
async def get_reconciliation_summary(ctx, args: dict) -> dict:
    """High-level summary of a reconciliation run's outcome."""
    require_view(ctx)
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not run_id:
        return {"error": "reconciliation_run_id is required."}
    try:
        run = await reconciliation_run_repository.get_by_id(
            ctx.db, ctx.workspace_id, run_id
        )
    except Exception:
        return {"run": {}, "message": "That reconciliation run wasn't found."}
    return {"run": _run_summary(run)}


@register_tool(
    "list_reconciliation_runs",
    description=(
        "List the most recent reconciliation runs in this workspace with their "
        "status and outcome counts. Use this to find the latest run when a "
        "question refers to 'the latest reconciliation' or when you have no run id."
    ),
    schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max runs to return (default 5, max 50)",
            }
        },
        "additionalProperties": False,
    },
)
async def list_reconciliation_runs(ctx, args: dict) -> dict:
    """List the most recent reconciliation runs in the workspace."""
    require_view(ctx)
    limit = args.get("limit") or 5
    page = await reconciliation_run_repository.list_runs(
        ctx.db, ctx.workspace_id, limit=int(limit)
    )
    return {"runs": [_run_summary(run) for run in page.items]}


@register_tool(
    "list_run_matches",
    description=(
        "List the persisted match decisions of a reconciliation run (optionally "
        "filtered by status). Use this to enumerate what matched, to compare "
        "confidence across records, or to inspect review candidates."
    ),
    schema={
        "type": "object",
        "properties": {
            "reconciliation_run_id": _OBJ_ID_PARAM,
            "statuses": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        ReconciliationStatus.MATCHED.value,
                        ReconciliationStatus.LIKELY_MATCH.value,
                        ReconciliationStatus.AMBIGUOUS.value,
                        ReconciliationStatus.MANUAL_MATCHED.value,
                    ],
                },
                "description": "Optional statuses to return (default: all)",
            },
            "limit": {
                "type": "integer",
                "description": "Max matches to return (default 20, max 200)",
            },
        },
        "additionalProperties": False,
    },
)
async def list_run_matches(ctx, args: dict) -> dict:
    """List a run's matches, optionally filtered by status."""
    require_view(ctx)
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not run_id:
        return {"error": "reconciliation_run_id is required."}
    try:
        run_oid = ObjectId(str(run_id))
    except Exception:
        return {"matches": [], "message": "That reconciliation run id isn't valid."}
    statuses = args.get("statuses") or None
    limit = args.get("limit") or 20
    page = await match_repository.list_matches_for_run(
        ctx.db, ctx.workspace_id, run_oid, statuses=statuses, limit=int(limit)
    )
    out = []
    for match in page.items:
        evidence = match.evidence or {}
        out.append(
            {
                "match_id": str(match.id),
                "transaction_ids": [str(t) for t in (match.transaction_ids or [])],
                "match_type": (
                    match.match_type.value
                    if hasattr(match.match_type, "value")
                    else str(match.match_type)
                ),
                "status": match.status,
                "confidence": str(match.confidence) if match.confidence is not None else None,
                "scoreBreakdown": {
                    k: str(v) for k, v in (evidence.get("scoreBreakdown") or {}).items()
                },
                "reasons": evidence.get("reasons") or [],
                "matchedFields": evidence.get("matchedFields") or [],
                "mismatchedFields": evidence.get("mismatchedFields") or [],
            }
        )
    return {"matches": out}


@register_tool(
    "list_run_exceptions",
    description=(
        "List the exceptions recorded for a reconciliation run (reason code, "
        "detail, status and linked transaction ids). Use this to answer e.g. "
        "'what exceptions do I need to review?' or to find exception patterns."
    ),
    schema={
        "type": "object",
        "properties": {
            "reconciliation_run_id": _OBJ_ID_PARAM,
            "limit": {
                "type": "integer",
                "description": "Max exceptions to return (default 20, max 200)",
            },
        },
        "additionalProperties": False,
    },
)
async def list_run_exceptions(ctx, args: dict) -> dict:
    """List a run's exceptions."""
    require_view(ctx)
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not run_id:
        return {"error": "reconciliation_run_id is required."}
    try:
        run_oid = ObjectId(str(run_id))
    except Exception:
        return {"exceptions": [], "message": "That reconciliation run id isn't valid."}
    limit = args.get("limit") or 20
    page = await exception_repository.list_for_run(
        ctx.db, ctx.workspace_id, run_oid, limit=int(limit)
    )
    return {
        "exceptions": [
            {
                "exception_id": str(exc.id),
                "reconciliation_run_id": str(exc.reconciliation_run_id),
                "transaction_ids": [str(t) for t in (exc.transaction_ids or [])],
                "reasonCode": (
                    exc.reason_code.value
                    if hasattr(exc.reason_code, "value")
                    else str(exc.reason_code)
                ),
                "detail": exc.detail,
                "status": (
                    exc.status.value if hasattr(exc.status, "value") else str(exc.status)
                ),
            }
            for exc in page.items
        ]
    }


@register_tool(
    "list_run_unmatched",
    description=(
        "List transactions in a run's scope that ended WITHOUT a match decision "
        "(A-side records that received no match group). Supports sorting by amount "
        "or date (e.g. sort_by='amount', order='desc' for highest-amount unmatched)."
    ),
    schema={
        "type": "object",
        "properties": {
            "reconciliation_run_id": _OBJ_ID_PARAM,
            "sort_by": {
                "type": "string",
                "enum": ["amount", "date"],
                "description": "Field to sort by: 'amount' (default) or 'date'",
            },
            "order": {
                "type": "string",
                "enum": ["desc", "asc"],
                "description": "Sort direction: 'desc' (default) or 'asc'",
            },
            "limit": {
                "type": "integer",
                "description": "Max unmatched transactions to return (default 20, max 200)",
            },
        },
        "additionalProperties": False,
    },
)
async def list_run_unmatched(ctx, args: dict) -> dict:
    """List a run's unmatched A-side transactions with sorting."""
    require_view(ctx)
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not run_id:
        return {"error": "reconciliation_run_id is required."}
    try:
        run = await reconciliation_run_repository.get_by_id(
            ctx.db, ctx.workspace_id, run_id
        )
    except Exception:
        return {"transactions": [], "message": "That reconciliation run wasn't found."}
    matched_ids = await match_repository.matched_transaction_ids_for_run(
        ctx.db, ctx.workspace_id, run.id
    )

    limit = int(args.get("limit") or 20)
    sort_by = str(args.get("sort_by") or "amount").lower()
    order = str(args.get("order") or "desc").lower()

    # Fetch records for sources excluding matched transactions
    page = await transaction_repository.list_transactions_for_sources(
        ctx.db,
        ctx.workspace_id,
        [ObjectId(s) for s in (run.source_ids or [])],
        transaction_repository.TransactionFilter(exclude_ids=list(matched_ids)),
        limit=200,  # retrieve enough to sort accurately
    )

    items = list(page.items)

    def _sort_key(t):
        if sort_by == "amount":
            try:
                return abs(float(t.amount)) if t.amount is not None else 0.0
            except Exception:
                return 0.0
        # sort by date
        if t.transaction_date:
            return t.transaction_date.isoformat()
        return ""

    items.sort(key=_sort_key, reverse=(order == "desc"))
    sliced = items[:limit]

    return {
        "total_unmatched_count": run.unmatched_count,
        "returned_count": len(sliced),
        "sorted_by": sort_by,
        "order": order,
        "transactions": [_txn_light(t) for t in sliced],
    }


def _txn_light(txn) -> dict:
    if txn is None:
        return {}
    return {
        "id": str(txn.id),
        "transaction_date": txn.transaction_date.isoformat() if getattr(txn, "transaction_date", None) else None,
        "amount": str(txn.amount) if getattr(txn, "amount", None) is not None else None,
        "currency": getattr(txn, "currency", None),
        "reference": getattr(txn, "reference", None),
        "counterparty": getattr(txn, "counterparty", None),
        "description": getattr(txn, "description", None),
        "source_id": str(txn.source_id) if getattr(txn, "source_id", None) else None,
        "status": getattr(txn, "status", None),
    }


@register_tool(
    "get_match_candidates",
    description=(
        "Candidates considered for one transaction within a run, including "
        "rejected and ambiguous candidates with their scores and reasons. Use "
        "this to explain why no candidate qualified for an unmatched transaction."
    ),
    schema={
        "type": "object",
        "properties": {
            "transaction_id": _OBJ_ID_PARAM,
            "reconciliation_run_id": _OBJ_ID_PARAM,
        },
        "required": ["transaction_id", "reconciliation_run_id"],
        "additionalProperties": False,
    },
)
async def get_match_candidates(ctx, args: dict) -> dict:
    """Candidates considered for one transaction within a run, with scores,
    reasons and status — evidence the engine saw, including rejections."""
    require_view(ctx)
    txn_id = args.get("transaction_id") or args.get("id")
    run_id = args.get("reconciliation_run_id") or args.get("run_id")
    if not txn_id or not run_id:
        return {"error": "transaction_id and reconciliation_run_id are required."}
    try:
        _txn_id = ObjectId(str(txn_id))
        _run_id = ObjectId(str(run_id))
    except Exception:
        return {"candidates": [], "message": "One of the ids isn't valid."}

    # Load candidates involving this transaction in this run (either side).
    candidates = await _candidates_for_txn(ctx.db, ctx.workspace_id, _txn_id, _run_id)

    out = []
    for c in candidates:
        partner_id = (
            c.transaction_b_id if c.transaction_a_id == _txn_id else c.transaction_a_id
        )
        row = {
            "candidate_id": str(c.id),
            "partner_id": str(partner_id),
            "score": str(c.score) if c.score is not None else None,
            "scoreBreakdown": {
                k: str(v) for k, v in (c.score_breakdown or {}).items()
            },
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "reasons": list(c.reasons),
        }
        partner = await transaction_repository.get_by_id(
            ctx.db, ctx.workspace_id, partner_id
        )
        row["partner"] = _txn_light(partner)
        out.append(row)
    return {"candidates": out}


async def _candidates_for_txn(db, workspace_id, txn_id, run_id):
    from ....models.match_candidate import MatchCandidate

    cursor = db["match_candidates"].find(
        {
            "workspaceId": workspace_id,
            "reconciliationRunId": run_id,
            "$or": [{"transactionAId": txn_id}, {"transactionBId": txn_id}],
        }
    )
    docs = await cursor.to_list(length=None)
    return [MatchCandidate.from_document(d) for d in docs]


def _iso(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)