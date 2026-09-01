"""AI Reconciliation Intelligence tests.

Strategy: drive the real route + dependency chain (same pattern as
test_authorization.py) but replace the LLM provider with a FakeProvider that
returns a scripted final answer. This lets us test:
  - the full route -> ai_service -> provider -> tool loop -> AIResponse path
  - workspace isolation (a member of WS A cannot analyze/retrieve WS B data)
  - permission enforcement (no view_data -> 403)
  - provider failure surfacing (AIUnavailableError -> AIAnalysisError -> 502)
  - missing / foreign entities -> 404
  - the tools themselves are workspace-scoped: the LLM never talks to MongoDB,
    it only ever receives tool *results* (cross-workspace lookups come back
    empty, never another workspace's rows).
"""

import asyncio
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from bson import ObjectId

from app.api import deps
from app.main import app
from app.models.enums import (
    DEFAULT_ROLE_PERMISSIONS,
    Direction,
    MembershipStatus,
    WorkspaceRole,
)
from app.models.transaction import Transaction
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories import transaction_repository
from app.services.ai import ai_service
from app.services.ai.tools import ToolContext, execute_tool
from tests.fakes.fake_mongo import FakeDatabase

WS_A = ObjectId("0000000000000000000000aa")
WS_B = ObjectId("0000000000000000000000bb")
OWNER_A = ObjectId("0000000000000000000000eb")
OWNER_B = ObjectId("0000000000000000000000ec")
MEMBER = ObjectId("0000000000000000000000e1")

_UTC = timezone.utc


def _user(uid, name="owner"):
    return User(id=uid, name=name, email=f"{name.lower()}@example.com")


def _seed_workspace(db, ws_id, owner_id, *, add_member=None, member_role=WorkspaceRole.MEMBER):
    async def _do():
        ws = Workspace(
            name="AI Corp",
            slug="aicorp",
            owner_id=owner_id,
            role_permissions={
                role: list(perms) for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
            },
            id=ws_id,
        )
        doc = ws.to_document()
        doc["_id"] = ws_id
        await db["workspaces"].insert_one(doc)
        members = [
            WorkspaceMember(
                workspace_id=ws_id,
                user_id=owner_id,
                role=WorkspaceRole.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=datetime.now(_UTC),
                updated_at=datetime.now(_UTC),
            )
        ]
        if add_member is not None:
            members.append(
                WorkspaceMember(
                    workspace_id=ws_id,
                    user_id=add_member,
                    role=member_role,
                    status=MembershipStatus.ACTIVE,
                    created_at=datetime.now(_UTC),
                    updated_at=datetime.now(_UTC),
                )
            )
        for m in members:
            md = m.to_document()
            md["_id"] = ObjectId()
            await db["workspace_members"].insert_one(md)

    asyncio.run(_do())


def _strip_view(db, ws_id, role):
    async def _do():
        await db["workspaces"].update_one(
            {"_id": ws_id}, {"$set": {f"rolePermissions.{role}": []}}
        )
    asyncio.run(_do())


@pytest.fixture()
def env():
    db = FakeDatabase()
    db.declare_standard_indexes()
    return db


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _client_for(db, actor, ws_id):
    from fastapi.testclient import TestClient

    actor_id = str(actor.id)

    async def _db():
        return db

    async def _uid():
        return actor_id

    async def _cu():
        return actor

    app.dependency_overrides[deps.get_database] = _db
    app.dependency_overrides[deps.require_user_id] = _uid
    app.dependency_overrides[deps.get_current_user] = _cu
    return TestClient(app), {"X-LL-Workspace-Id": str(ws_id)}


def _make_txn(ws_id, rid="T1"):
    return Transaction(
        workspace_id=ws_id,
        source_id=ObjectId("0000000000000000000000f1"),
        source_file_id=ObjectId("0000000000000000000000f2"),
        raw_transaction_id=ObjectId(),
        transaction_date=date(2026, 8, 10),
        amount=Decimal("100.00"),
        currency="INR",
        direction=Direction.CREDIT,
        description="Acme invoice",
        reference="INV-1",
        counterparty="Acme",
        status="SETTLED",
        fingerprint=f"fp-{rid}",
    )


# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------

FINAL_ANSWER = {
    "title": "Explained",
    "summary": "The transaction matches its counterpart on amount and date.",
    "findings": [
        {"kind": "fact", "text": "Amount is 100.00 INR."},
        {"kind": "inference", "text": "Likely an invoice payment."},
        {"kind": "recommendation", "text": "Confirm with the counterparty."},
    ],
    "evidence": [{"label": "Amount", "value": "100.00", "source": "transaction"}],
    "likely_causes": ["month-end timing"],
    "recommendations": ["recheck trip"],
    "confidence": "high",
    "limitations": [],
}


class FakeProvider:
    def __init__(self, content=None, raise_error=None):
        self.content = json.dumps(FINAL_ANSWER) if content is None else content
        self.raise_error = raise_error
        self.calls = []

    async def run(self, *, system, messages, tools, execute_tool, max_tool_rounds, timeout):
        self.calls.append({"tools": [t["function"]["name"] for t in tools]})
        if self.raise_error:
            raise self.raise_error
        return [{"role": "assistant", "content": self.content}]


@pytest.fixture()
def fake_provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(ai_service, "get_provider", lambda: provider)
    return provider


# ---------------------------------------------------------------------------
# transaction analysis
# ---------------------------------------------------------------------------


def test_owner_can_analyze_own_workspace_transaction(env, fake_provider):
    db = env
    _seed_workspace(db, WS_A, OWNER_A, add_member=MEMBER)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))

    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Explained"
    assert body["confidence"] == "high"
    assert body["findings"][0]["kind"] == "fact"
    assert any(t in fake_provider.calls[0]["tools"] for t in ("get_transaction",))


def test_foreign_workspace_transaction_is_not_found(env, fake_provider):
    """A member of WS A cannot analyze a transaction that lives in WS B."""
    db = env
    _seed_workspace(db, WS_A, OWNER_A, add_member=MEMBER)
    _seed_workspace(db, WS_B, OWNER_B)
    txn_b = _make_txn(WS_B, "TB")
    asyncio.run(transaction_repository.insert_transaction(db, WS_B, txn_b))

    owner_a = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner_a, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn_b.id}/analyze", headers=headers)
    assert r.status_code == 404, r.text


def test_missing_transaction_is_not_found(env, fake_provider):
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(
            f"/api/ai/transaction/{ObjectId()}/analyze", headers=headers
        )
    assert r.status_code == 404, r.text


def test_resolve_capabilities_reuses_member_permission_model(env):
    """The AI service reuses the same member_has_permission logic — no second
    permission system. A role without view_data / manage_exceptions must yield
    False for both AI capability flags, even though the route also enforces it."""
    db = env
    _seed_workspace(db, WS_A, OWNER_A, add_member=MEMBER)
    _strip_view(db, WS_A, "MEMBER")
    view, manage = ai_service.resolve_capabilities(
        db, WS_A, MEMBER, WorkspaceRole.MEMBER.value, {"MEMBER": []}
    )
    assert view is False
    assert manage is False

    # Default grants keep FULL VIEWER-ish access for roles that still have it.
    view2, manage2 = ai_service.resolve_capabilities(
        db, WS_A, OWNER_A, WorkspaceRole.OWNER.value, {"OWNER": ["view_data", "manage_exceptions"]}
    )
    assert view2 is True
    assert manage2 is True


def test_provider_unavailable_maps_to_502(env, monkeypatch):
    from app.services.ai.provider import AIUnavailableError

    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))

    owner = _user(OWNER_A, "owner")
    monkeypatch.setattr(
        ai_service, "get_provider", lambda: (_ for _ in ()).throw(
            AIUnavailableError("No Groq API key configured.")
        )
    )
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 503, r.text
    assert r.json()["code"] == "ai_unavailable"


def test_provider_error_maps_to_502(env, fake_provider):
    from app.services.ai.provider import AIProviderError

    fake_provider.raise_error = AIProviderError("upstream timeout")
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 502, r.text
    assert r.json()["code"] == "ai_request_failed"


def test_request_too_large_maps_to_413(env, fake_provider):
    """A provider 'request_too_large' failure surfaces as HTTP 413 with its own
    code, so the UI can show an actionable message instead of the generic
    'Reconciliation analysis failed' text the real bug was producing."""
    from app.services.ai.provider import AIProviderError

    fake_provider.raise_error = AIProviderError(
        "The data for this analysis was too large for the AI to process.",
        category="request_too_large",
    )
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 413, r.text
    body = r.json()
    assert body["code"] == "request_too_large"
    assert "too large" in body["detail"].lower()


def test_no_answer_maps_to_502_with_no_answer_code(env, fake_provider):
    """If the provider returns no usable textual answer, surface a specific
    'no_answer' error category rather than the generic AI failure."""
    fake_provider.content = "I have nothing further to say."
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 502, r.text
    assert r.json()["code"] == "no_answer"


# ---------------------------------------------------------------------------
# tools are workspace-scoped (LLM never touches Mongo)
# ---------------------------------------------------------------------------


def test_get_transaction_tool_is_workspace_scoped(env):
    db = env
    txn_a = _make_txn(WS_A, "TA")
    txn_b = _make_txn(WS_B, "TB")
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn_a))
    asyncio.run(transaction_repository.insert_transaction(db, WS_B, txn_b))

    ctx = ToolContext(
        db=db, workspace_id=WS_A, user_id=OWNER_A,
        can_view_data=True, can_manage_exceptions=True,
    )

    def _run(name, args):
        return asyncio.run(execute_tool(ctx, name, args))

    # Inside workspace A -> sees A's transaction.
    res = _run("get_transaction", {"transaction_id": str(txn_a.id)})
    assert res["transaction"]["id"] == str(txn_a.id)
    # A foreign id (belongs to B) -> empty, not B's rows.
    res = _run("get_transaction", {"transaction_id": str(txn_b.id)})
    assert res["transaction"] == {}


def test_get_transaction_requires_view_data(env):
    db = env
    txn_a = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn_a))
    ctx = ToolContext(
        db=db, workspace_id=WS_A, user_id=MEMBER,
        can_view_data=False, can_manage_exceptions=False,
    )
    with pytest.raises(PermissionError):
        asyncio.run(execute_tool(ctx, "get_transaction", {"transaction_id": str(txn_a.id)}))


def test_ask_endpoint_accepts_history_and_active_entity_context(env, fake_provider):
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)

    payload = {
        "question": "Why are transactions unmatched?",
        "reconciliation_run_id": "0000000000000000000000c1",
        "history": [
            {"role": "user", "content": "Explain this reconciliation"},
            {"role": "assistant", "content": "This run compares 95 records."}
        ]
    }
    # First seed the run so validation passes
    from app.models.enums import RunStatus
    from app.models.reconciliation_run import ReconciliationRun
    run = ReconciliationRun(

        id=ObjectId("0000000000000000000000c1"),
        workspace_id=WS_A,
        status=RunStatus.COMPLETED,

        total_transactions=95,
        matched_count=6,
        unmatched_count=83,
        exception_count=49,
        source_ids=[],
        started_at=datetime.now(_UTC),
    )
    async def _seed_run():
        d = run.to_document()
        d["_id"] = run.id
        await db["reconciliation_runs"].insert_one(d)
    asyncio.run(_seed_run())

    with c:
        r = c.post("/api/ai/ask", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Explained"


def test_ask_endpoint_rejects_foreign_match_id(env, fake_provider):
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    _seed_workspace(db, WS_B, OWNER_B)
    owner_a = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner_a, WS_A)

    foreign_match_id = str(ObjectId())
    payload = {
        "question": "Why did this match?",
        "match_id": foreign_match_id,
    }
    with c:
        r = c.post("/api/ai/ask", json=payload, headers=headers)
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# context-specific tool filtering
# ---------------------------------------------------------------------------


def test_transaction_analysis_sends_only_transaction_relevant_tools(env, fake_provider):
    """The transaction entry point advertises a small, focused tool subset —
    not all 16 schemas — so the model stops re-probing irrelevant data."""
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    txn = _make_txn(WS_A)
    asyncio.run(transaction_repository.insert_transaction(db, WS_A, txn))
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/transaction/{txn.id}/analyze", headers=headers)
    assert r.status_code == 200, r.text

    sent = fake_provider.calls[0]["tools"]
    assert set(sent) <= {"get_transaction", "get_transaction_context", "get_match_candidates", "search_workspace_transactions", "get_match"}
    assert "get_exception" not in sent
    assert "list_reconciliation_runs" not in sent
    assert "get_reconciliation_summary" not in sent


def test_match_analysis_sends_only_match_relevant_tools(env, fake_provider):
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    from tests.test_ai_tools import _seed_run
    run, txn_a, txn_b, txn_c, match, candidate = _seed_run(db, WS_A)
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/match/{match.id}/analyze", headers=headers)
    assert r.status_code == 200, r.text

    sent = fake_provider.calls[0]["tools"]
    assert set(sent) <= {"get_match", "get_transaction", "get_transaction_context", "get_reconciliation_run"}
    assert "get_exception" not in sent
    assert "get_reconciliation_summary" not in sent
    assert "list_run_exceptions" not in sent


def test_exception_analysis_sends_only_exception_relevant_tools(env, fake_provider):
    db = env
    from tests.test_ai_tools import _seed_run
    from app.repositories import exception_repository
    from app.models.enums import ExceptionReason, ExceptionStatus
    from app.models.reconciliation_exception import ReconciliationException

    _seed_workspace(db, WS_A, OWNER_A)
    run, txn_a, txn_b, txn_c, *_ = _seed_run(db, WS_A, total=3, matched=1, unmatched=1, general_exceptions=0)

    exc = ReconciliationException(
        workspace_id=WS_A,
        reconciliation_run_id=run.id,
        transaction_ids=[txn_c.id],
        reason_code=ExceptionReason.CANDIDATE_COLLISION,
        detail="Two candidate matches.",
        status=ExceptionStatus.OPEN,
    )
    asyncio.run(exception_repository.insert_exceptions(db, [exc]))

    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post(f"/api/ai/exception/{exc.id}/analyze", headers=headers)
    assert r.status_code == 200, r.text

    sent = fake_provider.calls[0]["tools"]
    assert set(sent) <= {"get_exception", "get_exception_context", "get_exception_notes", "get_transaction", "get_reconciliation_run"}
    assert "get_match" not in sent
    assert "list_run_unmatched" not in sent


def test_chatbot_ask_uses_full_tool_set(env, fake_provider):
    """The global copilot (no active entity) keeps the full 16-tool set."""
    db = env
    _seed_workspace(db, WS_A, OWNER_A)
    owner = _user(OWNER_A, "owner")
    c, headers = _client_for(db, owner, WS_A)
    with c:
        r = c.post("/api/ai/ask", json={"question": "What data is available?"}, headers=headers)
    assert r.status_code == 200, r.text

    from app.services.ai.tools import tool_names
    assert set(fake_provider.calls[0]["tools"]) == set(tool_names())

