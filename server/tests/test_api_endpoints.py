"""API-level tests through the FastAPI app with dependency overrides.

Auth is provided by overrides (the Next.js boundary owns real auth); the
database is the in-memory fake so no MongoDB is required."""

import pytest
from bson import ObjectId

from app.api import deps
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import workspace_repository
from app.services.source_service import create_source
from tests.fakes.fake_mongo import FakeDatabase

USER_ID = ObjectId("0000000000000000000000aa")


def csv_content(gateway_only_row: bool = False) -> bytes:
    rows = (
        b"TxnId,Date,Amount,Currency,Description,Reference,Counterparty\n"
        b"P1,2026-08-10,1500.00,INR,PAYMENT ABC PVT LTD,NEFT1001,ABC PVT LTD\n"
        b"P2,2026-08-10,-250.50,,UTILITY BILL XYZ,,\n"
        b"P3,2026-08-11,4200.75,INR,NEFT CREDIT QRS,UTR77,QRS LIMITED\n"
        b"BAD,not-a-date,5.00,INR,broken,,\n"
    )
    if gateway_only_row:
        rows += b"GX1,2026-08-12,999.99,INR,GATEWAY ONLY CAPTURE,GWX1,LONE BUYER\n"
    return rows


@pytest.fixture()
def db_env():
    db = FakeDatabase()
    db.declare_standard_indexes()
    return db


@pytest.fixture()
def workspace(db_env):
    import asyncio
    from datetime import datetime, timezone

    from app.models.enums import MembershipStatus, WorkspaceRole
    from app.models.workspace_member import WorkspaceMember

    ws = Workspace(name="Test Co", slug="test-co", owner_id=USER_ID,
                   id=ObjectId("00000000000000000000a001"))

    # Seed the actor as OWNER so permission enforcement (require_permission)
    # passes for the shared endpoints being exercised here.
    async def _seed():
        await db_env["workspace_members"].insert_one(
            WorkspaceMember(
                workspace_id=ws.id,
                user_id=USER_ID,
                role=WorkspaceRole.OWNER,
                status=MembershipStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ).to_document()
        )

    asyncio.run(_seed())
    return ws


@pytest.fixture()
def client(db_env, workspace):
    from fastapi.testclient import TestClient

    user = User(id=USER_ID, name="Tester", email="tester@example.com")

    async def _db():
        return db_env

    async def _user_id():
        return str(USER_ID)

    async def _current_user():
        return user

    async def _workspace():
        return workspace

    app.dependency_overrides[deps.get_database] = _db
    app.dependency_overrides[deps.require_user_id] = _user_id
    app.dependency_overrides[deps.get_current_user] = _current_user
    app.dependency_overrides[deps.get_current_workspace] = _workspace
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def unauth_client(db_env):
    from fastapi.testclient import TestClient

    async def _db():
        return db_env

    app.dependency_overrides[deps.get_database] = _db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_source(client, name, type_="BANK"):
    response = client.post("/api/sources", json={
        "name": name, "type": type_, "currency": "INR",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_missing_internal_secret_is_unauthorized(unauth_client):
    response = unauth_client.get("/api/sources")
    assert response.status_code == 401


def test_create_and_list_sources(client):
    created = _create_source(client, "HDFC Main")
    assert created["name"] == "HDFC Main"
    assert created["type"] == "BANK"
    assert created["currency"] == "INR"

    listing = client.get("/api/sources").json()
    assert len(listing["items"]) == 1
    assert listing["items"][0]["id"] == created["id"]

    duplicate_name = client.post("/api/sources", json={
        "name": "HDFC Main", "type": "BANK", "currency": "INR",
    })
    assert duplicate_name.status_code == 409


def test_upload_files_and_transactions_pagination(client):
    bank = _create_source(client, "Bank A", "BANK")
    gateway = _create_source(client, "Gateway B", "PAYMENT_PROCESSOR")

    first = client.post(
        f"/api/files/upload?sourceId={bank['id']}&fileName=aug.csv&mimeType=text/csv",
        content=csv_content(),
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["isDuplicate"] is False
    assert body["file"]["status"] == "PARTIAL"   # one broken row on purpose
    assert body["file"]["transactionCount"] == 3

    replay = client.post(
        f"/api/files/upload?sourceId={bank['id']}&fileName=aug-copy.csv&mimeType=text/csv",
        content=csv_content(),
    )
    assert replay.status_code == 201
    assert replay.json()["isDuplicate"] is True

    page_one = client.get(f"/api/transactions?limit=2&sourceId={bank['id']}").json()
    assert len(page_one["items"]) == 2
    assert page_one["page"]["nextCursor"]

    page_two = client.get(
        f"/api/transactions?limit=2&sourceId={bank['id']}"
        f"&cursor={page_one['page']['nextCursor']}"
    ).json()
    seen_ids = {item["id"] for item in page_one["items"]} | \
               {item["id"] for item in page_two["items"]}
    assert len(seen_ids) == 3   # no overlap, everything reachable

    filtered = client.get("/api/transactions?dateFrom=2026-08-11").json()
    assert all(item["transactionDate"].startswith("2026-08-11") for item in filtered["items"])

    bad_cursor = client.get("/api/transactions?cursor=@@@not-a-cursor@@@")
    assert bad_cursor.status_code == 400


def test_reconciliation_run_end_to_end_via_api(client):
    bank = _create_source(client, "Bank Run A", "BANK")
    gateway = _create_source(client, "Gateway Run B", "PAYMENT_PROCESSOR")

    for source in (bank, gateway):
        uploaded = client.post(
            f"/api/files/upload?sourceId={source['id']}&fileName={source['name']}.csv"
            f"&mimeType=text/csv",
            content=csv_content(gateway_only_row=source is gateway),
        )
        assert uploaded.status_code == 201

    started = client.post("/api/reconciliations", json={
        "sourceIds": [bank["id"], gateway["id"]],
    })
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["status"] == "COMPLETED"
    assert run["algorithmVersion"]
    assert run["config"]["weight_amount"] == "0.35"
    assert run["totalTransactions"] == 7   # bank 3 + gateway 4 (one broken row excluded)

    single = client.get(f"/api/reconciliations/{run['id']}")
    assert single.status_code == 200

    matches = client.get(f"/api/reconciliations/{run['id']}/matches").json()
    assert matches["items"], "expected at least one match document"

    exceptions = client.get(f"/api/reconciliations/{run['id']}/exceptions").json()
    assert exceptions["items"], "broken row + leftovers must raise exceptions"
    assert all(item["status"] == "OPEN" for item in exceptions["items"])

    missing_run = client.get(f"/api/reconciliations/{ObjectId()}/matches")
    assert missing_run.status_code == 404


def test_invalid_payloads_are_rejected(client):
    too_few_sources = client.post("/api/reconciliations", json={"sourceIds": ["x"]})
    assert too_few_sources.status_code in (422, 400)

    bad_currency = client.post("/api/sources", json={
        "name": "Bad", "type": "BANK", "currency": "ZZZ",
    })
    assert bad_currency.status_code == 422


def test_transaction_search_filters_by_text(client):
    bank = _create_source(client, "Search Bank", "BANK")
    uploaded = client.post(
        f"/api/files/upload?sourceId={bank['id']}&fileName=search.csv&mimeType=text/csv",
        content=csv_content(),
    )
    assert uploaded.status_code == 201

    hits = client.get("/api/transactions?search=neft1001").json()
    assert len(hits["items"]) == 1
    assert hits["items"][0]["reference"] == "NEFT1001"

    hits = client.get("/api/transactions?search=utility").json()
    assert len(hits["items"]) == 1

    misses = client.get("/api/transactions?search=does-not-exist-anywhere").json()
    assert misses["items"] == []


def test_transaction_matches_endpoint_returns_evidence(client):
    bank = _create_source(client, "Evidence Bank", "BANK")
    gateway = _create_source(client, "Evidence Gateway", "PAYMENT_PROCESSOR")
    for source in (bank, gateway):
        client.post(
            f"/api/files/upload?sourceId={source['id']}&fileName={source['name']}.csv"
            f"&mimeType=text/csv",
            content=csv_content(gateway_only_row=source is gateway),
        )

    started = client.post("/api/reconciliations", json={
        "sourceIds": [bank["id"], gateway["id"]],
    })
    run = started.json()

    matches = client.get(f"/api/reconciliations/{run['id']}/matches").json()
    first_match = matches["items"][0]
    involved_id = first_match["transactionIds"][0]

    evidence = client.get(f"/api/transactions/{involved_id}/matches")
    assert evidence.status_code == 200, evidence.text
    body = evidence.json()
    assert any(m["id"] == first_match["id"] for m in body["items"])
    assert body["items"][0]["scoreBreakdown"]

    # A transaction with no match returns an empty page, not an error.
    all_txns = client.get("/api/transactions?limit=50").json()
    lone = next(t for t in all_txns["items"] if t["id"] not in {
        i for m in matches["items"] for i in m["transactionIds"]
    })
    empty = client.get(f"/api/transactions/{lone['id']}/matches").json()
    assert empty["items"] == []

    unknown = client.get(f"/api/transactions/{ObjectId()}/matches")
    assert unknown.status_code == 404


def test_run_matches_status_filter_and_unmatched_endpoint(client):
    bank = _create_source(client, "Unmatched Bank", "BANK")
    gateway = _create_source(client, "Unmatched Gateway", "PAYMENT_PROCESSOR")
    for source in (bank, gateway):
        client.post(
            f"/api/files/upload?sourceId={source['id']}&fileName={source['name']}.csv"
            f"&mimeType=text/csv",
            content=csv_content(gateway_only_row=source is gateway),
        )

    started = client.post("/api/reconciliations", json={
        "sourceIds": [bank["id"], gateway["id"]],
    })
    run = started.json()
    assert run["unmatchedCount"] >= 1

    matched_only = client.get(
        f"/api/reconciliations/{run['id']}/matches?status=MATCHED"
    ).json()
    assert matched_only["items"]
    assert all(item["status"] == "MATCHED" for item in matched_only["items"])

    # Multiple statuses combine with $in semantics (used by the review tab).
    review = client.get(
        f"/api/reconciliations/{run['id']}/matches"
        "?status=LIKELY_MATCH&status=AMBIGUOUS"
    ).json()
    assert all(item["status"] in {"LIKELY_MATCH", "AMBIGUOUS"} for item in review["items"])
    combined = {
        *{m["id"] for m in client.get(
            f"/api/reconciliations/{run['id']}/matches?status=LIKELY_MATCH").json()["items"]},
        *{m["id"] for m in client.get(
            f"/api/reconciliations/{run['id']}/matches?status=AMBIGUOUS").json()["items"]},
    }
    assert {m["id"] for m in review["items"]} == combined

    unmatched = client.get(f"/api/reconciliations/{run['id']}/unmatched").json()
    assert unmatched["items"], "the gateway-only row must be unmatched"
    assert all(item["sourceId"] in {bank["id"], gateway["id"]} for item in unmatched["items"])

    match_ids = {i for m in matched_only["items"] for i in m["transactionIds"]}
    assert not {item["id"] for item in unmatched["items"]} & match_ids

    missing = client.get(f"/api/reconciliations/{ObjectId()}/unmatched")
    assert missing.status_code == 404


def test_workspace_exceptions_feed_and_overview_summary(client):
    bank = _create_source(client, "Feed Bank", "BANK")
    gateway = _create_source(client, "Feed Gateway", "PAYMENT_PROCESSOR")
    for source in (bank, gateway):
        client.post(
            f"/api/files/upload?sourceId={source['id']}&fileName={source['name']}.csv"
            f"&mimeType=text/csv",
            content=csv_content(gateway_only_row=source is gateway),
        )
    client.post("/api/reconciliations", json={"sourceIds": [bank["id"], gateway["id"]]})

    feed = client.get("/api/exceptions").json()
    assert feed["items"], "workspace-wide exception feed must include run exceptions"
    assert all(item["status"] == "OPEN" for item in feed["items"])

    open_only = client.get("/api/exceptions?status=OPEN").json()
    assert len(open_only["items"]) == len(feed["items"])

    none_resolved = client.get("/api/exceptions?status=RESOLVED").json()
    assert none_resolved["items"] == []

    overview = client.get("/api/overview").json()
    assert overview["totalTransactions"] == 7
    assert overview["sourcesCount"] == 2
    assert overview["openExceptions"] == len(feed["items"])
    assert overview["latestRun"]["status"] == "COMPLETED"
    assert overview["latestRun"]["totalTransactions"] == 7
