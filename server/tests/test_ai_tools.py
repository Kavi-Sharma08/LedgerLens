"""Tests for the AI tool registry and the reconciliation tools.

These cover the pieces that the existing route-level AI tests do not: the
discovery tools (get_transaction_context, list_reconciliation_runs,
list_run_matches, list_run_exceptions, list_run_unmatched), both-side candidate
lookup, workspace scoping of the new tools, and the failure semantics of
execute_tool (unknown tool -> AIProviderError, NOT a fake "no data" dict).

Every retrieval goes through the real repository layer against the fake Mongo,
so these tests double as a regression guard for the repository calls the tools
depend on.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from bson import ObjectId

from app.models.enums import (
    CandidateStatus,
    Direction,
    ExceptionReason,
    ExceptionStatus,
    MatchType,
    MembershipStatus,
    RunStatus,
    SourceType,
    WorkspaceRole,
)
from app.models.match import Match
from app.models.match_candidate import MatchCandidate
from app.models.reconciliation_exception import ReconciliationException
from app.models.reconciliation_run import ReconciliationRun
from app.models.source import Source
from app.models.transaction import Transaction
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories import (
    exception_repository,
    match_repository,
    reconciliation_run_repository,
    source_repository,
    transaction_repository,
)
from app.services.ai.provider import AIProviderError
from app.services.ai.tools import ToolContext, execute_tool, tool_names

WS_A = ObjectId("0000000000000000000000aa")
WS_B = ObjectId("0000000000000000000000bb")
OWNER_A = ObjectId("0000000000000000000000eb")
OWNER_B = ObjectId("0000000000000000000000ec")

_UTC = timezone.utc


def _txn(ws_id, rid):
    return Transaction(
        workspace_id=ws_id,
        source_id=ObjectId("0000000000000000000000f1"),
        source_file_id=ObjectId("0000000000000000000000f2"),
        raw_transaction_id=ObjectId(),
        transaction_date=date(2026, 8, 10),
        amount=Decimal("100.00"),
        currency="INR",
        direction=Direction.CREDIT,
        description=f"Invoice {rid}",
        reference=f"INV-{rid}",
        counterparty="Acme",
        status="SETTLED",
        fingerprint=f"fp-{rid}",
    )


def _seed_workspace(db, ws_id, owner_id):
    async def _do():
        ws = Workspace(
            name="AI Corp",
            slug="aicorp",
            owner_id=owner_id,
            role_permissions={},
            id=ws_id,
        )
        doc = ws.to_document()
        doc["_id"] = ws_id
        await db["workspaces"].insert_one(doc)
        member = WorkspaceMember(
            workspace_id=ws_id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            status=MembershipStatus.ACTIVE,
            created_at=datetime.now(_UTC),
            updated_at=datetime.now(_UTC),
        )
        md = member.to_document()
        md["_id"] = ObjectId()
        await db["workspace_members"].insert_one(md)

    asyncio.run(_do())


def _seed_run(db, ws_id, *, total=3, matched=1, unmatched=1, general_exceptions=1):
    async def _do():
        source = Source(
            workspace_id=ws_id,
            name="HDFC Bank",
            type=SourceType.BANK,
            institution="HDFC",
            currency="INR",
        )
        await source_repository.create_source(db, ws_id, source)

        run = ReconciliationRun(
            workspace_id=ws_id,
            source_ids=[source.id],
            status=RunStatus.COMPLETED,
            transaction_scope={"dateFrom": "2026-08-01", "dateTo": "2026-08-31"},
            started_at=datetime(2026, 8, 20, 10, 0, tzinfo=_UTC),
            completed_at=datetime(2026, 8, 20, 10, 1, tzinfo=_UTC),
            total_transactions=total,
            matched_count=matched,
            likely_match_count=0,
            ambiguous_count=0,
            unmatched_count=unmatched,
            exception_count=general_exceptions,
            algorithm_version="1.0-test",
        )
        await reconciliation_run_repository.create_run(db, ws_id, run)

        txn_a = _txn(ws_id, "TA")
        txn_b = _txn(ws_id, "TB")
        txn_c = _txn(ws_id, "TC")
        txn_a.source_id = source.id
        txn_b.source_id = source.id
        txn_c.source_id = source.id
        for t in (txn_a, txn_b, txn_c):
            await transaction_repository.insert_transaction(db, ws_id, t)

        candidate = MatchCandidate(
            workspace_id=ws_id,
            reconciliation_run_id=run.id,
            transaction_a_id=txn_a.id,
            transaction_b_id=txn_b.id,
            score=Decimal("0.95"),
            score_breakdown={"amountScore": 1.0, "dateScore": 0.9, "referenceScore": 1.0},
            reasons=["amount_match", "date_within_tolerance", "reference_match"],
            status=CandidateStatus.SELECTED,
        )
        await match_repository.insert_candidate(db, candidate)

        match = Match(
            workspace_id=ws_id,
            reconciliation_run_id=run.id,
            transaction_ids=[txn_a.id, txn_b.id],
            match_type=MatchType.FUZZY,
            status="MATCHED",
            confidence=Decimal("0.95"),
            evidence={
                "scoreBreakdown": {"amountScore": 1.0, "dateScore": 0.9, "referenceScore": 1.0},
                "reasons": ["amount_match", "date_within_tolerance", "reference_match"],
                "tolerancesUsed": {"dateToleranceDays": 3, "amountTolerancePercent": 0.05},
                "matchedFields": ["amount", "reference"],
                "mismatchedFields": [],
            },
algorithm_version="1.0-test",
        )
        await match_repository.insert_match(db, match)

        if general_exceptions:
            await exception_repository.insert_exceptions(
                db,
                [
                    ReconciliationException(
                        workspace_id=ws_id,
                        reconciliation_run_id=run.id,
                        transaction_ids=[txn_c.id],
                        reason_code=ExceptionReason.CANDIDATE_COLLISION,
                        detail="Two near-identical candidate rows.",
                        status=ExceptionStatus.OPEN,
                    ),
                    ReconciliationException(
                        workspace_id=ws_id,
                        reconciliation_run_id=run.id,
                        transaction_ids=[txn_a.id],
                        reason_code=ExceptionReason.FAILED_TRANSACTION,
                        detail="Counterparty record is in FAILED state.",
                        status=ExceptionStatus.OPEN,
                    ),
                ],
            )

        return run, txn_a, txn_b, txn_c, match, candidate

    return asyncio.run(_do())


def _ctx(db, ws_id, can_view=True):
    return ToolContext(
        db=db,
        workspace_id=ws_id,
        user_id=OWNER_A,
        can_view_data=can_view,
        can_manage_exceptions=True,
    )


def _run_tool(ctx, name, args):
    return asyncio.run(execute_tool(ctx, name, args))


@pytest.fixture()
def env():
    from tests.fakes.fake_mongo import FakeDatabase

    db = FakeDatabase()
    db.declare_standard_indexes()
    return db


@pytest.fixture()
def seeded(env):
    """A completed run in WS_A with two matched and one unmatched txn."""
    run, txn_a, txn_b, txn_c, match, candidate = _seed_run(env, WS_A)
    return {
        "db": env,
        "run": run,
        "match": match,
        "candidate": candidate,
        "txn_a": txn_a,
        "txn_b": txn_b,
        "txn_c": txn_c,
    }


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def test_all_tools_have_descriptions_and_property_schemas(env):
    """Regression guard for the 'empty parameters block' bug that produced
    malformed tool calls / provider 400s."""
    from app.services.ai.tools import tool_schemas

    for t in tool_schemas():
        fn = t["function"]
        assert fn["name"], fn
        description = fn.get("description") or ""
        assert len(description) > 40, f"{fn['name']} description too short"
        params = fn["parameters"]
        assert params.get("type") == "object"
        assert isinstance(params.get("properties"), dict), fn["name"]
        assert "additionalProperties" in params, fn["name"]


def test_tool_names_are_unique_and_expected(env):
    names = set(tool_names())
    for expected in (
        "get_transaction_context",
        "get_reconciliation_run",
        "get_match",
        "get_match_candidates",
        "list_reconciliation_runs",
        "list_run_matches",
        "list_run_exceptions",
        "list_run_unmatched",
    ):
        assert expected in names


# ---------------------------------------------------------------------------
# get_transaction_context
# ---------------------------------------------------------------------------


def test_get_transaction_context_returns_matches_candidates_exceptions_runs(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "get_transaction_context", {"transaction_id": str(seeded["txn_a"].id)})

    assert res["transaction"]["id"] == str(seeded["txn_a"].id)

    assert len(res["matches"]) == 1
    match = res["matches"][0]
    assert match["match_id"] == str(seeded["match"].id)
    assert match["transaction_ids"] == [str(seeded["txn_a"].id), str(seeded["txn_b"].id)]
    assert match["scoreBreakdown"]["amountScore"] == "1.0"
    assert match["matchedFields"] == ["amount", "reference"]
    assert match["tolerancesUsed"]["dateToleranceDays"] == 3

    assert len(res["candidates"]) == 1
    cand = res["candidates"][0]
    assert cand["partner_id"] == str(seeded["txn_b"].id)
    assert cand["score"] == "0.95"
    assert cand["status"] == "SELECTED"
    assert cand["partner"]["id"] == str(seeded["txn_b"].id)

    assert len(res["exceptions"]) == 1
    assert res["exceptions"][0]["reasonCode"] == "FAILED_TRANSACTION"

    assert len(res["runs"]) == 1
    assert res["runs"][0]["totalTransactions"] == 3
    assert res["runs"][0]["matchedCount"] == 1


def test_get_transaction_context_finds_candidates_on_both_sides(seeded):
    """The candidate store records transactionBId too: a transaction that was
    the B side must still be discoverable."""
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "get_transaction_context", {"transaction_id": str(seeded["txn_b"].id)})
    assert len(res["candidates"]) == 1
    assert res["candidates"][0]["partner_id"] == str(seeded["txn_a"].id)
    assert len(res["matches"]) == 1  # match group contains txn_b as well


def test_get_transaction_context_is_workspace_scoped(env):
    run, txn_a, *_ = _seed_run(env, WS_A)
    other = _txn(WS_B, "ZB")
    asyncio.run(transaction_repository.insert_transaction(env, WS_B, other))

    ctx_a = _ctx(env, WS_A)
    res_a = _run_tool(ctx_a, "get_transaction_context", {"transaction_id": str(txn_a.id)})
    assert res_a["transaction"]["id"] == str(txn_a.id)

    # A foreign txn id from WS_B queried against WS_A -> not found.
    res_foreign = _run_tool(ctx_a, "get_transaction_context", {"transaction_id": str(other.id)})
    assert res_foreign["transaction"] == {}
    assert "wasn't found" in res_foreign["message"]

    # The same foreign id IS found when queried from WS_B's context.
    ctx_b = _ctx(env, WS_B)
    assert _run_tool(ctx_b, "get_transaction_context", {"transaction_id": str(other.id)})["transaction"]["id"] == str(other.id)


def test_get_transaction_context_requires_view_data(seeded):
    ctx = _ctx(seeded["db"], WS_A, can_view=False)
    with pytest.raises(PermissionError):
        _run_tool(ctx, "get_transaction_context", {"transaction_id": str(seeded["txn_a"].id)})


# ---------------------------------------------------------------------------
# run-level discovery tools
# ---------------------------------------------------------------------------


def test_list_reconciliation_runs(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "list_reconciliation_runs", {})
    assert len(res["runs"]) == 1
    run = res["runs"][0]
    assert run["id"] == str(seeded["run"].id)
    assert run["totalTransactions"] == 3
    assert "countsNote" in run


def test_list_run_matches(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "list_run_matches", {"reconciliation_run_id": str(seeded["run"].id)})
    assert len(res["matches"]) == 1
    m = res["matches"][0]
    assert m["match_id"] == str(seeded["match"].id)
    assert m["matchedFields"] == ["amount", "reference"]
    assert len(m["transaction_ids"]) == 2


def test_list_run_matches_filters_by_status(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(
        ctx,
        "list_run_matches",
        {"reconciliation_run_id": str(seeded["run"].id), "statuses": ["AMBIGUOUS"]},
    )
    assert res["matches"] == []


def test_list_run_exceptions(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "list_run_exceptions", {"reconciliation_run_id": str(seeded["run"].id)})
    assert len(res["exceptions"]) == 2
    assert {e["reasonCode"] for e in res["exceptions"]} == {"CANDIDATE_COLLISION", "FAILED_TRANSACTION"}
    exc = next(e for e in res["exceptions"] if e["reasonCode"] == "CANDIDATE_COLLISION")
    assert exc["transaction_ids"] == [str(seeded["txn_c"].id)]


def test_list_run_unmatched_excludes_matched_and_returns_leftovers(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(ctx, "list_run_unmatched", {"reconciliation_run_id": str(seeded["run"].id)})
    ids = [t["id"] for t in res["transactions"]]
    assert ids == [str(seeded["txn_c"].id)]
    assert str(seeded["txn_a"].id) not in ids
    assert str(seeded["txn_b"].id) not in ids
    # Verify description and status are populated
    assert res["transactions"][0]["description"] is not None


def test_list_run_unmatched_sorts_by_amount_descending(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    # Seed an extra unmatched transaction with larger amount in the run's source scope
    db = seeded["db"]
    big_txn = _txn(WS_A, "big")
    big_txn.source_id = seeded["run"].source_ids[0]
    big_txn.amount = Decimal("50000.00")
    md = big_txn.to_document()
    md["_id"] = ObjectId()
    big_txn.id = md["_id"]
    asyncio.run(db["transactions"].insert_one(md))

    res = _run_tool(
        ctx,
        "list_run_unmatched",
        {"reconciliation_run_id": str(seeded["run"].id), "sort_by": "amount", "order": "desc", "limit": 10},
    )
    txns = res["transactions"]
    assert len(txns) >= 2
    assert txns[0]["id"] == str(big_txn.id)
    assert float(txns[0]["amount"]) == 50000.0



def test_get_match_candidates_in_run_works(seeded):
    ctx = _ctx(seeded["db"], WS_A)
    res = _run_tool(
        ctx,
        "get_match_candidates",
        {
            "transaction_id": str(seeded["txn_a"].id),
            "reconciliation_run_id": str(seeded["run"].id),
        },
    )
    assert len(res["candidates"]) == 1
    cand = res["candidates"][0]
    assert cand["scoreBreakdown"]["amountScore"] == "1.0"
    assert cand["reasons"] == ["amount_match", "date_within_tolerance", "reference_match"]


# ---------------------------------------------------------------------------
# execute_tool failure semantics
# ---------------------------------------------------------------------------


def test_unknown_tool_raises_and_never_masks_as_no_data(env):
    ctx = _ctx(env, WS_A)
    with pytest.raises(AIProviderError) as exc:
        _run_tool(ctx, "does_not_exist", {})
    assert exc.value.category == "tool_execution_failed"


def test_malformed_transaction_id_is_a_normal_tool_result(env):
    """A bad id is 'no data', not a crash — the model must handle both."""
    ctx = _ctx(env, WS_A)
    res = _run_tool(ctx, "get_transaction_context", {"transaction_id": "not-an-objectid"})
    assert res["transaction"] == {}
    assert "isn't valid" in res["message"]
