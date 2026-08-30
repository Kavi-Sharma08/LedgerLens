"""AI tools for transaction evidence.

All retrieval is workspace-scoped via the shared repositories; a foreign or
unknown id simply returns an empty/not-found result. Only the fields needed
for analysis are returned (no full Mongo documents) to control token cost.

`get_transaction_context` is the discovery entry-point a transaction analysis
starts with: it resolves the transaction to its persisted match(es), scored
candidate pairs (including rejected ones), exceptions and reconciliation
run(s) so the LLM can explain a matched, unmatched, likely-match or exception
outcome without ever touching MongoDB directly.
"""

from __future__ import annotations

from bson import ObjectId

from ....repositories import (
    exception_repository,
    match_repository,
    reconciliation_run_repository,
    transaction_repository,
)
from ..tools import register_tool, require_view

_OBJ_ID_PARAM = {"type": "string", "description": "24-character MongoDB ObjectId"}


def _txn_evidence(txn) -> dict:
    if txn is None:
        return {}
    return {
        "id": str(txn.id),
        "sourceId": str(txn.source_id),
        "transaction_date": (
            txn.transaction_date.isoformat() if txn.transaction_date else None
        ),
        "amount": str(txn.amount) if txn.amount is not None else None,
        "currency": txn.currency,
        "direction": txn.direction.value if hasattr(txn.direction, "value") else str(txn.direction),
        "description": txn.description,
        "reference": txn.reference,
        "counterparty": txn.counterparty,
        "transaction_type": txn.transaction_type,
        "status": txn.status,
    }


@register_tool(
    "get_transaction",
    description=(
        "Retrieve one transaction's key fields by id. Use this when the question "
        "is about the transaction itself (amount, date, reference, counterparty, "
        "direction, status)."
    ),
    schema={
        "type": "object",
        "properties": {"transaction_id": _OBJ_ID_PARAM},
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
)
async def get_transaction(ctx, args: dict) -> dict:
    """Retrieve one transaction's key fields by id."""
    require_view(ctx)
    txn_id = args.get("transaction_id") or args.get("id")
    if not txn_id:
        return {"error": "transaction_id is required."}
    try:
        _id = ObjectId(str(txn_id))
    except Exception:
        return {"transaction": {}, "message": "That transaction id isn't valid."}
    txn = await transaction_repository.get_by_id(ctx.db, ctx.workspace_id, _id)
    return {"transaction": _txn_evidence(txn)}


@register_tool(
    "get_transaction_context",
    description=(
        "Retrieve the full reconciliation context of ONE transaction: its stored "
        "match(es) (score, matched/mismatched fields, reasons), every scored "
        "candidate pair it was considered with (including rejected/ambiguous "
        "candidates and their scores), any exceptions referencing it, and the "
        "reconciliation run(s) involved. START here for any question about why a "
        "transaction was matched, left unmatched, or flagged for review."
    ),
    schema={
        "type": "object",
        "properties": {"transaction_id": _OBJ_ID_PARAM},
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
)
async def get_transaction_context(ctx, args: dict) -> dict:
    """Resolve one transaction to its matches, candidates, exceptions and runs."""
    require_view(ctx)
    txn_id = args.get("transaction_id") or args.get("id")
    if not txn_id:
        return {"error": "transaction_id is required."}
    try:
        oid = ObjectId(str(txn_id))
    except Exception:
        return {
            "transaction": {},
            "matches": [],
            "candidates": [],
            "exceptions": [],
            "message": "That transaction id isn't valid.",
        }
    txn = await transaction_repository.get_by_id(ctx.db, ctx.workspace_id, oid)
    if txn is None:
        return {
            "transaction": {},
            "matches": [],
            "candidates": [],
            "exceptions": [],
            "message": "That transaction wasn't found in this workspace.",
        }

    result = {
        "transaction": _txn_evidence(txn),
        "matches": [],
        "candidates": [],
        "exceptions": [],
    }
    run_ids: list[ObjectId] = []

    match_page = await match_repository.list_for_transaction(ctx.db, ctx.workspace_id, oid)
    for match in match_page.items:
        evidence = match.evidence or {}
        result["matches"].append(
            {
                "match_id": str(match.id),
                "reconciliation_run_id": str(match.reconciliation_run_id),
                "match_type": (
                    match.match_type.value
                    if hasattr(match.match_type, "value")
                    else str(match.match_type)
                ),
                "status": match.status,
                "confidence": str(match.confidence) if match.confidence is not None else None,
                "transaction_ids": [str(t) for t in (match.transaction_ids or [])],
                "scoreBreakdown": {
                    k: str(v) for k, v in (evidence.get("scoreBreakdown") or {}).items()
                },
                "reasons": evidence.get("reasons") or [],
                "matchedFields": evidence.get("matchedFields") or [],
                "mismatchedFields": evidence.get("mismatchedFields") or [],
                "tolerancesUsed": evidence.get("tolerancesUsed") or {},
            }
        )
        run_ids.append(match.reconciliation_run_id)
        for tid in (match.transaction_ids or []):
            if tid != oid:
                partner = await transaction_repository.get_by_id(
                    ctx.db, ctx.workspace_id, tid
                )
                if partner is not None:
                    result.setdefault("partners", []).append(_txn_evidence(partner))

    from ....models.match_candidate import MatchCandidate

    candidate_docs = await ctx.db["match_candidates"].find(
        {
            "workspaceId": ctx.workspace_id,
            "$or": [{"transactionAId": oid}, {"transactionBId": oid}],
        }
    ).to_list(length=None)
    for doc in candidate_docs:
        candidate = MatchCandidate.from_document(doc)
        partner_id = (
            candidate.transaction_b_id
            if candidate.transaction_a_id == oid
            else candidate.transaction_a_id
        )
        partner = await transaction_repository.get_by_id(
            ctx.db, ctx.workspace_id, partner_id
        )
        row = {
            "candidate_id": str(candidate.id),
            "reconciliation_run_id": str(candidate.reconciliation_run_id),
            "partner_id": str(partner_id),
            "score": str(candidate.score) if candidate.score is not None else None,
            "scoreBreakdown": {
                k: str(v) for k, v in (candidate.score_breakdown or {}).items()
            },
            "reasons": list(candidate.reasons),
            "status": (
                candidate.status.value
                if hasattr(candidate.status, "value")
                else str(candidate.status)
            ),
            "partner": _txn_light(partner),
        }
        result["candidates"].append(row)
        run_ids.append(candidate.reconciliation_run_id)

    exc_docs = await ctx.db["exceptions"].find(
        {"workspaceId": ctx.workspace_id, "transactionIds": oid}
    ).to_list(length=None)
    for doc in exc_docs:
        from ....models.reconciliation_exception import ReconciliationException

        exc = ReconciliationException.from_document(doc)
        result["exceptions"].append(
            {
                "exception_id": str(exc.id),
                "reconciliation_run_id": str(exc.reconciliation_run_id),
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
        )
        run_ids.append(exc.reconciliation_run_id)

    runs = []
    seen = set()
    for run_id in run_ids:
        if run_id in seen:
            continue
        seen.add(run_id)
        try:
            run = await reconciliation_run_repository.get_by_id(
                ctx.db, ctx.workspace_id, run_id
            )
        except Exception:
            continue
        runs.append(
            {
                "id": str(run.id),
                "status": (
                    run.status.value if hasattr(run.status, "value") else str(run.status)
                ),
                "totalTransactions": run.total_transactions,
                "matchedCount": run.matched_count,
                "likelyMatchCount": run.likely_match_count,
                "ambiguousCount": run.ambiguous_count,
                "unmatchedCount": run.unmatched_count,
                "exceptionCount": run.exception_count,
            }
        )
    result["runs"] = runs
    return result


@register_tool(
    "search_workspace_transactions",
    description=(
        "Search transactions in the current workspace (or scoped to a reconciliation run) "
        "by a text query against reference, description or counterparty. Returns up to 8 matches."
    ),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-text search terms"},
            "reconciliation_run_id": _OBJ_ID_PARAM,
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)
async def search_workspace_transactions(ctx, args: dict) -> dict:
    """Search transactions in the current workspace by a text query."""
    require_view(ctx)
    query = (args.get("query") or "").strip()
    if not query:
        return {"error": "query is required."}
    from ....repositories.transaction_repository import TransactionFilter

    run_id = args.get("reconciliation_run_id")
    if run_id:
        try:
            run = await reconciliation_run_repository.get_by_id(ctx.db, ctx.workspace_id, run_id)
            if run and run.source_ids:
                page = await transaction_repository.list_transactions_for_sources(
                    ctx.db,
                    ctx.workspace_id,
                    [ObjectId(s) for s in run.source_ids],
                    TransactionFilter(search=query),
                    limit=8,
                )
                return {"transactions": [_txn_evidence(t) for t in page.items]}
        except Exception:
            pass

    page = await transaction_repository.list_transactions(
        ctx.db,
        ctx.workspace_id,
        TransactionFilter(search=query),
        limit=8,
    )
    return {"transactions": [_txn_evidence(t) for t in page.items]}



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
    }