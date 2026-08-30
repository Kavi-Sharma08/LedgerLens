"""Regression suite for the "default OWNER lost their workspace" report.

Pins the API boundary contracts that the dashboard depends on after login:

  - a signed-in OWNER automatically resolves their ACTIVE workspace (the
    ll-active-workspace cookie may be missing/stale — the workspace list and
    /current fallback must still return the user's real workspace);
  - OWNER always has full permissions regardless of rolePermissions;
  - OWNER can read reconciliation results (runs, matches, exceptions,
    unmatched) for their workspace;
  - a missing/stale workspace header is rejected (404/403) and NEVER falls
    through to another tenant's data — the browser falls back to the first
    listed workspace instead;
  - switching between two owned workspaces returns only that workspace's data;
  - MEMBER/VIEWER read access is preserved but write/reconciliation actions
    stay permission-gated;
  - the AI routes are mounted alongside the normal API and share the exact
    same workspace + view_data gate (no second, leaky authorization path).

These run the REAL get_current_workspace / require_permission dependency chain
with the in-memory FakeDatabase (only the trusted identity boundary is faked),
mirroring test_authorization.py.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone

from bson import ObjectId

from app.api import deps
from app.main import app
from app.models.enums import (
    DEFAULT_ROLE_PERMISSIONS,
    MembershipStatus,
    WorkspaceRole,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.fakes.fake_mongo import FakeDatabase
import pytest

WS_MAIN = ObjectId("00000000000000000000e001")
WS_SECOND = ObjectId("00000000000000000000e002")
FOREIGN_WS = ObjectId("00000000000000000000e003")

OWNER_ID = ObjectId("00000000000000000000f001")
OTHER_USER_ID = ObjectId("00000000000000000000f002")
MEMBER_ID = ObjectId("00000000000000000000f003")
VIEWER_ID = ObjectId("00000000000000000000f004")


def _user(uid, name):
    return User(id=uid, name=name, email=f"{name}@example.com")


def _seed_roles(db, ws_id, role_permissions):
    """Insert the workspace doc and (by default) an OWNER live membership."""
    async def _do():
        ws = Workspace(
            name="Main Co",
            slug="main-web-111",
            owner_id=OWNER_ID,
            role_permissions=role_permissions,
            id=ws_id,
        )
        doc = ws.to_document()
        doc["_id"] = ws_id
        await db["workspaces"].insert_one(doc)
    asyncio.run(_do())


def _seed_membership(db, ws_id, user_id, role, status=MembershipStatus.ACTIVE):
    async def _do():
        m = WorkspaceMember(
            workspace_id=ws_id,
            user_id=user_id,
            role=role,
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        md = m.to_document()
        md["_id"] = ObjectId()
        await db["workspace_members"].insert_one(md)
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


@contextmanager
def client_for(db, actor: User):
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _headers(ws_id):
    return {"X-LL-Workspace-Id": str(ws_id)}


def _csv():
    return (
        b"TxnId,Date,Amount,Currency,Description,Reference,Counterparty\n"
        b"P1,2026-08-10,1500.00,INR,PAYMENT ABC PVT LTD,NEFT1001,ABC PVT LTD\n"
        b"P2,2026-08-10,-250.50,,UTILITY BILL XYZ,,\n"
        b"P3,2026-08-11,4200.75,INR,NEFT CREDIT QRS,UTR77,QRS LIMITED\n"
        b"BAD,not-a-date,5.00,INR,broken,,\n"
    )


def _seed_run_data(client, ws_id):
    """Create two sources, upload evidence, run reconciliation. Returns run id."""
    ids = []
    for name, type_ in (("Bank A", "BANK"), ("Gateway B", "PAYMENT_PROCESSOR")):
        r = client.post(
            "/api/sources",
            json={"name": name, "type": type_, "currency": "INR"},
            headers=_headers(ws_id),
        )
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    for sid, file_name in zip(ids, ("aug.csv", "aug-gw.csv")):
        r = client.post(
            f"/api/files/upload?sourceId={sid}&fileName={file_name}&mimeType=text/csv",
            content=_csv(),
            headers=_headers(ws_id),
        )
        assert r.status_code == 201, r.text
    r = client.post(
        "/api/reconciliations",
        json={"sourceIds": ids},
        headers=_headers(ws_id),
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1) default OWNER -> workspace resolution
# ---------------------------------------------------------------------------


def test_default_owner_resolves_own_workspace_without_cookie(env):
    """With NO ll-active-workspace cookie, the signed-in OWNER must still get
    their real workspace: the unscoped list answers with it and /current
    falls back to the first ACTIVE membership. Foreign workspaces never leak
    into the list."""
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)
    _seed_roles(env, FOREIGN_WS, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, FOREIGN_WS, OTHER_USER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        listed = c.get("/api/workspaces")
        assert listed.status_code == 200, listed.text
        names = [w["id"] for w in listed.json()]
        assert str(WS_MAIN) in names
        assert str(FOREIGN_WS) not in names   # not the actor's workspace

        current = c.get("/api/workspaces/current")
        assert current.status_code == 200, current.text
        assert current.json()["id"] == str(WS_MAIN)


def test_stale_cookie_falls_back_to_first_valid_workspace(env, monkeypatch):
    """A stale ll-active-workspace id (a membership that no longer exists) is
    rejected server-side with 403 — the data endpoints must never fall through.
    The frontend resolves that 403 by falling back to the workspace LIST, which
    is unchanged and unscoped, so the user still lands on a valid workspace."""
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)

    stale = ObjectId("00000000000000000000eeee")
    owner = _user(OWNER_ID, "owner")

    with client_for(env, owner) as c:
        r = c.get("/api/sources", headers=_headers(stale))
        assert r.status_code == 403, r.text

        listed = c.get("/api/workspaces").json()
        assert [w["id"] for w in listed] == [str(WS_MAIN)]  # unchanged fallback source


# ---------------------------------------------------------------------------
# 2) OWNER permissions ignore rolePermissions
# ---------------------------------------------------------------------------


def test_owner_always_has_full_permissions_even_with_empty_role_permissions(env):
    _seed_roles(env, WS_MAIN, {})  # oddly configured: no grants recorded at all
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        r = c.get("/api/sources", headers=_headers(WS_MAIN))
        assert r.status_code == 200, r.text
        r = c.post(
            "/api/sources",
            json={"name": "Owner Bank", "type": "BANK", "currency": "INR"},
            headers=_headers(WS_MAIN),
        )
        assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 3) OWNER reads reconciliation data
# ---------------------------------------------------------------------------


def test_owner_can_read_reconciliation_results(env):
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        run_id = _seed_run_data(c, WS_MAIN)

        r = c.get(f"/api/reconciliations/{run_id}", headers=_headers(WS_MAIN))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "COMPLETED"

        for sub, key in (
            ("matches", "items"),
            ("exceptions", "items"),
            ("unmatched", "items"),
        ):
            r = c.get(f"/api/reconciliations/{run_id}/{sub}", headers=_headers(WS_MAIN))
            assert r.status_code == 200, r.text
            assert key in r.json()

    # And matches must exist, proving data actually flows to the UI.
    with client_for(env, owner) as c:
        matches = c.get(
            f"/api/reconciliations/{run_id}/matches", headers=_headers(WS_MAIN)
        ).json()
        assert matches["items"], "a completed run over this dataset must yield matches"


# ---------------------------------------------------------------------------
# 4) missing / invalid workspace context
# ---------------------------------------------------------------------------


def test_missing_workspace_header_is_404_not_data_leak(env):
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        r = c.get("/api/sources")  # nothing but the X-LL-Workspace-Id omitted
        assert r.status_code == 404, r.text
        assert "No workspace selected" in r.json()["detail"]


def test_foreign_workspace_is_403(env):
    """A workspace the user is not a member of (and does not own) is rejected
    before any data query — never a cross-tenant leak."""
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)
    _seed_roles(env, FOREIGN_WS, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, FOREIGN_WS, OTHER_USER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        r = c.get("/api/sources", headers=_headers(FOREIGN_WS))
        assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 5) valid workspace switching
# ---------------------------------------------------------------------------


def test_valid_workspace_switching_returns_each_workspaces_own_data(env):
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)
    _seed_roles(env, WS_SECOND, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_SECOND, OWNER_ID, WorkspaceRole.OWNER)

    owner = _user(OWNER_ID, "owner")
    for ws_id, name in ((WS_MAIN, "Main Source"), (WS_SECOND, "Second Source")):
        with client_for(env, owner) as c:
            r = c.post(
                "/api/sources",
                json={"name": name, "type": "BANK", "currency": "INR"},
                headers=_headers(ws_id),
            )
            assert r.status_code == 201, r.text

    with client_for(env, owner) as c:
        main_sources = c.get("/api/sources", headers=_headers(WS_MAIN)).json()["items"]
        second_sources = c.get("/api/sources", headers=_headers(WS_SECOND)).json()["items"]
        assert [s["name"] for s in main_sources] == ["Main Source"]
        assert [s["name"] for s in second_sources] == ["Second Source"]


# ---------------------------------------------------------------------------
# 6) MEMBER / VIEWER read-only enforcement
# ---------------------------------------------------------------------------


def test_member_and_viewer_read_data_but_cannot_run_reconciliation(env):
    _seed_roles(env, WS_MAIN, DEFAULT_ROLE_PERMISSIONS)
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)
    _seed_membership(env, WS_MAIN, MEMBER_ID, WorkspaceRole.MEMBER)
    _seed_membership(env, WS_MAIN, VIEWER_ID, WorkspaceRole.VIEWER)

    owner = _user(OWNER_ID, "owner")
    source_ids = []
    with client_for(env, owner) as c:
        for name in ("Bank A", "Gateway B"):
            r = c.post(
                "/api/sources",
                json={"name": name, "type": "BANK", "currency": "INR"},
                headers=_headers(WS_MAIN),
            )
            source_ids.append(r.json()["id"])

    for who, actor in (("member", _user(MEMBER_ID, "member")),
                       ("viewer", _user(VIEWER_ID, "viewer"))):
        with client_for(env, actor) as c:
            read = c.get("/api/sources", headers=_headers(WS_MAIN))
            assert read.status_code == 200, f"{who} must be able to read data"
            run = c.post(
                "/api/reconciliations",
                json={"sourceIds": source_ids},
                headers=_headers(WS_MAIN),
            )
            assert run.status_code == 403, f"{who} must not run reconciliation by default"


# ---------------------------------------------------------------------------
# 7) AI isolation: same workspace + view_data gate, normal API unaffected
# ---------------------------------------------------------------------------


def test_ai_routes_share_view_data_gate_and_leave_normal_api_alone(env):
    _seed_roles(env, WS_MAIN, {"MEMBER": []})  # member grants: nothing
    _seed_membership(env, WS_MAIN, OWNER_ID, WorkspaceRole.OWNER)
    _seed_membership(env, WS_MAIN, MEMBER_ID, WorkspaceRole.MEMBER)

    # AI router is really mounted on the shared app (Starlette keeps included
    # routers lazy, so assert via the generated OpenAPI schema).
    paths = app.openapi().get("paths", {})
    assert "/api/ai/ask" in paths
    assert "/api/ai/transaction/{transaction_id}/analyze" in paths

    # A member with no view_data hits the SAME 403 on the AI endpoint that a
    # normal data endpoint returns — the AI layer adds no back door.
    member = _user(MEMBER_ID, "member")
    with client_for(env, member) as c:
        normal = c.get("/api/sources", headers=_headers(WS_MAIN))
        assert normal.status_code == 403, normal.text
        ai = c.post(
            "/api/ai/ask",
            json={"question": "how many transactions?"},
            headers=_headers(WS_MAIN),
        )
        assert ai.status_code == 403, ai.text

    # The owner's normal access is completely unaffected by the AI addition.
    owner = _user(OWNER_ID, "owner")
    with client_for(env, owner) as c:
        r = c.get("/api/sources", headers=_headers(WS_MAIN))
        assert r.status_code == 200, r.text