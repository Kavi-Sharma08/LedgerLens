"""Backend-enforced authorization tests.

These run the REAL get_current_workspace / require_permission dependency chain
(no workspace override). Only the trusted identity boundary is faked: the
actor is fixed via require_user_id + get_current_user overrides, and each
request carries X-LL-Workspace-Id so the real workspace resolution, membership
verification, and per-role permission checks all execute against the in-memory
database.

Covers: OWNER/ADMIN/MEMBER/VIEWER authorized + unauthorized operations (403),
owner-only permission management, ownership/role-change constraints, and the
server-side enforcement that UI-only guards replaced.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
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

WS_ID = ObjectId("0000000000000000000000c0")
OWNER_ID = ObjectId("0000000000000000000000d1")
ADMIN_ID = ObjectId("0000000000000000000000d2")
MEMBER_ID = ObjectId("0000000000000000000000d3")
VIEWER_ID = ObjectId("0000000000000000000000d4")

ACTORS = {
    "owner": (OWNER_ID, WorkspaceRole.OWNER),
    "admin": (ADMIN_ID, WorkspaceRole.ADMIN),
    "member": (MEMBER_ID, WorkspaceRole.MEMBER),
    "viewer": (VIEWER_ID, WorkspaceRole.VIEWER),
}


def _user(uid: ObjectId, name: str) -> User:
    return User(id=uid, name=name, email=f"{name}@example.com")


def _seed_workspace(db: FakeDatabase) -> None:
    async def _do():
        ws = Workspace(
            name="AuthCorp",
            slug="authcorp",
            owner_id=OWNER_ID,
            role_permissions={
                role: list(perms) for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
            },
            id=WS_ID,
        )
        ws_doc = ws.to_document()
        ws_doc["_id"] = WS_ID
        await db["workspaces"].insert_one(ws_doc)
        for _, (uid, role) in ACTORS.items():
            m = WorkspaceMember(
                workspace_id=WS_ID,
                user_id=uid,
                role=role,
                status=MembershipStatus.ACTIVE,
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
    _seed_workspace(db)
    return db


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@contextmanager
def client_for(db, actor: User, ws_id: ObjectId):
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


def _headers():
    return {"X-LL-Workspace-Id": str(WS_ID)}


def _create_sources(db, owner: User):
    """Create two sources as owner. Returns their ids."""
    with client_for(db, owner, WS_ID) as c:
        ids = []
        for name in ("Bank A", "Gateway B"):
            r = c.post(
                "/api/sources",
                json={"name": name, "type": "BANK", "currency": "INR"},
                headers=_headers(),
            )
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
    return ids


def test_owner_can_manage_sources_and_viewer_cannot(env):
    owner = _user(OWNER_ID, "owner")
    viewer = _user(VIEWER_ID, "viewer")

    with client_for(env, owner, WS_ID) as c:
        r = c.post(
            "/api/sources",
            json={"name": "Bank A", "type": "BANK", "currency": "INR"},
            headers=_headers(),
        )
        assert r.status_code == 201, r.text

    with client_for(env, viewer, WS_ID) as c:
        r = c.post(
            "/api/sources",
            json={"name": "Bank B", "type": "BANK", "currency": "INR"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_member_default_is_read_only(env):
    member = _user(MEMBER_ID, "member")

    with client_for(env, member, WS_ID) as c:
        # Member can view sources (view_data grant)...
        r = c.get("/api/sources", headers=_headers())
        assert r.status_code == 200, r.text
        # ...but cannot create one (no manage_sources by default).
        r = c.post(
            "/api/sources",
            json={"name": "Bank A", "type": "BANK", "currency": "INR"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_upload_files_enforced_per_role(env):
    owner = _user(OWNER_ID, "owner")
    admin = _user(ADMIN_ID, "admin")
    member = _user(MEMBER_ID, "member")

    src_id = _create_sources(env, owner)[0]
    body = b"TxnId,Date,Amount,Currency\nX,2026-08-10,1.00,INR\n"

    with client_for(env, admin, WS_ID) as c:
        # ADMIN default grant includes upload_files -> allowed.
        r = c.post(
            "/api/files/upload",
            params={"sourceId": src_id, "fileName": "a.csv"},
            content=body,
            headers=_headers(),
        )
        assert r.status_code == 201, r.text

    with client_for(env, member, WS_ID) as c:
        # MEMBER default is view-only -> upload forbidden server-side.
        r = c.post(
            "/api/files/upload",
            params={"sourceId": src_id, "fileName": "a.csv"},
            content=body,
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_run_reconciliation_enforced_per_role(env):
    owner = _user(OWNER_ID, "owner")
    admin = _user(ADMIN_ID, "admin")
    member = _user(MEMBER_ID, "member")

    src_ids = _create_sources(env, owner)

    with client_for(env, admin, WS_ID) as c:
        r = c.post(
            "/api/reconciliations",
            json={"sourceIds": src_ids},
            headers=_headers(),
        )
        assert r.status_code == 201, r.text

    with client_for(env, member, WS_ID) as c:
        r = c.post(
            "/api/reconciliations",
            json={"sourceIds": src_ids},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_viewer_cannot_manage_members_or_remove_owner(env):
    owner = _user(OWNER_ID, "owner")
    viewer = _user(VIEWER_ID, "viewer")

    with client_for(env, viewer, WS_ID) as c:
        r = c.patch(
            f"/api/workspaces/{WS_ID}/members/{MEMBER_ID}",
            json={"role": "ADMIN"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_admin_cannot_demote_owner_or_change_own_role(env):
    owner = _user(OWNER_ID, "owner")
    admin = _user(ADMIN_ID, "admin")

    with client_for(env, admin, WS_ID) as c:
        # Admin (default has manage_members) cannot demote the owner.
        r = c.patch(
            f"/api/workspaces/{WS_ID}/members/{OWNER_ID}",
            json={"role": "MEMBER"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text
        # Admin cannot change their own role (self-modification forbidden).
        r = c.patch(
            f"/api/workspaces/{WS_ID}/members/{ADMIN_ID}",
            json={"role": "MEMBER"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text


def test_only_owner_can_invite_admin(env):
    owner = _user(OWNER_ID, "owner")
    admin = _user(ADMIN_ID, "admin")

    with client_for(env, admin, WS_ID) as c:
        r = c.post(
            f"/api/workspaces/{WS_ID}/invitations",
            json={"email": "newbie@example.com", "role": "ADMIN"},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text

    with client_for(env, owner, WS_ID) as c:
        r = c.post(
            f"/api/workspaces/{WS_ID}/invitations",
            json={"email": "newbie@example.com", "role": "MEMBER"},
            headers=_headers(),
        )
        assert r.status_code == 201, r.text


def test_only_owner_manages_workspace_permissions(env):
    owner = _user(OWNER_ID, "owner")
    admin = _user(ADMIN_ID, "admin")

    with client_for(env, admin, WS_ID) as c:
        r = c.patch(
            f"/api/workspaces/{WS_ID}/permissions",
            json={"role": "MEMBER", "permissions": ["view_data"]},
            headers=_headers(),
        )
        assert r.status_code == 403, r.text

    with client_for(env, owner, WS_ID) as c:
        r = c.patch(
            f"/api/workspaces/{WS_ID}/permissions",
            json={"role": "MEMBER", "permissions": ["view_data"]},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text


def test_owner_grant_enables_member_action_and_revoke_denies(env):
    owner = _user(OWNER_ID, "owner")
    member = _user(MEMBER_ID, "member")

    src_ids = _create_sources(env, owner)

    with client_for(env, member, WS_ID) as c:
        assert c.post(
            "/api/reconciliations",
            json={"sourceIds": src_ids},
            headers=_headers(),
        ).status_code == 403

    with client_for(env, owner, WS_ID) as c:
        r = c.patch(
            f"/api/workspaces/{WS_ID}/permissions",
            json={
                "role": "MEMBER",
                "permissions": ["view_data", "run_reconciliation"],
            },
            headers=_headers(),
        )
        assert r.status_code == 200, r.text

    with client_for(env, member, WS_ID) as c:
        r = c.post(
            "/api/reconciliations",
            json={"sourceIds": src_ids},
            headers=_headers(),
        )
        assert r.status_code == 201, r.text

    # Revoke and confirm the member is denied again.
    with client_for(env, owner, WS_ID) as c:
        r = c.patch(
            f"/api/workspaces/{WS_ID}/permissions",
            json={"role": "MEMBER", "permissions": ["view_data"]},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text

    with client_for(env, member, WS_ID) as c:
        assert c.post(
            "/api/reconciliations",
            json={"sourceIds": src_ids},
            headers=_headers(),
        ).status_code == 403


def test_member_can_manage_notes_but_not_status(env):
    """Investigation notes are open to any active member with view_data, while
    status changes still require manage_exceptions (owner/admin only)."""
    owner = _user(OWNER_ID, "owner")
    member = _user(MEMBER_ID, "member")
    exc_id = ObjectId()

    def seed():
        async def _do():
            from datetime import datetime, timezone
            from app.models.reconciliation_exception import ReconciliationException

            e = ReconciliationException(
                id=exc_id,
                workspace_id=WS_ID,
                reconciliation_run_id=ObjectId(),
                transaction_ids=[],
                notes=[],
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            doc = e.to_document()
            doc["_id"] = exc_id
            await env["exceptions"].insert_one(doc)

        asyncio.run(_do())

    seed()

    # MEMBER (default view_data) can create, then edit and delete a note.
    with client_for(env, member, WS_ID) as c:
        created = c.post(
            f"/api/exceptions/{exc_id}/notes",
            json={"text": "A member insight"},
            headers=_headers(),
        )
        assert created.status_code == 200, created.text
        note = created.json()
        assert note["text"] == "A member insight"
        assert note["createdBy"]

        updated = c.patch(
            f"/api/exceptions/{exc_id}/notes/{note['id']}",
            json={"text": "A member insight (edited)"},
            headers=_headers(),
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["text"] == "A member insight (edited)"

        deleted = c.delete(
            f"/api/exceptions/{exc_id}/notes/{note['id']}", headers=_headers()
        )
        assert deleted.status_code == 200, deleted.text

    # MEMBER cannot change status (manage_exceptions is not granted to MEMBER).
    with client_for(env, member, WS_ID) as c:
        assert (
            c.patch(
                f"/api/exceptions/{exc_id}/status",
                json={"status": "RESOLVED"},
                headers=_headers(),
            ).status_code
            == 403
        )

    # OWNER can still manage status.
    with client_for(env, owner, WS_ID) as c:
        r = c.patch(
            f"/api/exceptions/{exc_id}/status",
            json={"status": "RESOLVED"},
            headers=_headers(),
        )
        assert r.status_code == 200, r.text
