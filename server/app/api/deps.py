"""Shared FastAPI dependencies.

Authentication boundary
=======================
Auth.js (Next.js) is the ONLY authentication authority. FastAPI performs no
OAuth, issues no tokens, and stores no sessions of its own.

Trusted identity arrives on server-to-server calls from the Next.js boundary
(client/src/app/api/backend/[...path]/route.js) as:

    X-LL-User-Id        stable MongoDB user id, minted from the Auth.js token
    X-LL-User-Email     user email (URI-encoded)
    X-LL-Internal-Sec   INTERNAL_API_SECRET shared with Next.js
    X-LL-Workspace-Id   active workspace id chosen by the browser

The internal secret gates every authenticated endpoint: a browser cannot call
FastAPI directly because it can never know the secret, and identity headers
sent without it are rejected. The secret is compared in constant time.

Workspace context
=================
The user's *choice* of active workspace is sent as X-LL-Workspace-Id. The
backend verifies that the authenticated user actually has an active
membership in that workspace before any data operation. A forged workspace
header is rejected at this boundary — the browser cannot address another
tenant's financial data.
"""

import hmac
import logging
from functools import wraps

from fastapi import Depends, Request

from ..core.config import get_settings
from ..core.database import get_database
from ..core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from ..models.enums import MembershipStatus, WorkspaceRole, user_has_permission
from ..models.user import User
from ..models.workspace import Workspace
from ..models.workspace_member import WorkspaceMember
from ..repositories import user_repository, workspace_repository
from ..repositories import workspace_member_repository as member_repo

logger = logging.getLogger("ledgerlens.deps")

USER_ID_HEADER = "x-ll-user-id"
INTERNAL_SECRET_HEADER = "x-ll-internal-secret"
WORKSPACE_ID_HEADER = "x-ll-workspace-id"


def _authorized(request: Request) -> bool:
    expected = get_settings().internal_api_secret
    provided = request.headers.get(INTERNAL_SECRET_HEADER, "")
    return bool(expected) and hmac.compare_digest(provided.encode(), expected.encode())


async def require_user_id(request: Request) -> str:
    """Validate the trusted-forwarding contract only — no database access.

    Kept separate so requests failing the boundary check fail fast with 401,
    even while the database is unreachable.
    """
    if not _authorized(request):
        logger.warning("Rejected call missing or failing internal auth (%s)", request.url.path)
        raise UnauthorizedError()

    user_id = request.headers.get(USER_ID_HEADER, "")
    if not user_id:
        raise UnauthorizedError()
    return user_id


async def get_current_user(
    user_id: str = Depends(require_user_id),
    db=Depends(get_database),
) -> User:
    """Resolve the signed-in user identified by the Next.js boundary."""
    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        raise UnauthorizedError()
    return user


async def get_current_workspace(
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db=Depends(get_database),
) -> Workspace:
    """Trusted workspace context for every financial endpoint.

    The workspace id comes from X-LL-Workspace-Id (the user's choice), but
    membership is verified server-side. A forged header is rejected."""
    workspace_id = request.headers.get(WORKSPACE_ID_HEADER, "") if request else ""

    if not workspace_id:
        raise NotFoundError(message="No workspace selected. Choose a workspace first.")

    # Verify membership
    member = await member_repo.get_member(db, workspace_id, current_user.id)
    if member is None or member.status != MembershipStatus.ACTIVE:
        raise ForbiddenError(message="You don't have access to this workspace.")

    workspace = await workspace_repository.get_by_id(db, workspace_id)
    if workspace is None:
        raise NotFoundError(message="That workspace doesn't exist.")
    return workspace


def require_permission(permission: str):
    """Dependency factory: verify the current user has the named permission.

    Usage in routes:
        @router.post("/sources")
        async def create_source(
            _=Depends(require_permission("create_source")),
            ...
        )
    """
    async def _check(
        current_user: User = Depends(get_current_user),
        workspace: Workspace = Depends(get_current_workspace),
        db=Depends(get_database),
    ):
        member = await member_repo.get_member(db, workspace.id, current_user.id)
        if member is None or member.status != MembershipStatus.ACTIVE:
            raise ForbiddenError(message="You don't have access to this workspace.")
        if not user_has_permission(member.role, permission):
            raise ForbiddenError(
                message=f"You don't have permission to do this. Required role: {permission}."
            )
        return member
    return _check


async def get_current_membership(
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db=Depends(get_database),
) -> WorkspaceMember:
    """Return the current user's membership record for the active workspace."""
    member = await member_repo.get_member(db, workspace.id, current_user.id)
    if member is None or member.status != MembershipStatus.ACTIVE:
        raise ForbiddenError(message="You don't have access to this workspace.")
    return member
