"""Shared FastAPI dependencies.

Authentication boundary
=======================
Auth.js (Next.js) is the ONLY authentication authority. FastAPI performs no
OAuth, issues no tokens, and stores no sessions of its own.

Trusted identity arrives on server-to-server calls from the Next.js boundary
(client/src/app/api/backend/[...path]/route.js) as:

    X-LL-User-Id        stable MongoDB user id, minted from the Auth.js token
    X-LL-Internal-Sec   INTERNAL_API_SECRET shared with Next.js

The internal secret gates every authenticated endpoint: a browser cannot call
FastAPI directly because it can never know the secret, and identity headers
sent without it are rejected. The secret is compared in constant time.
"""

import hmac
import logging

from fastapi import Depends, Request

from ..core.config import get_settings
from ..core.database import get_database
from ..core.errors import NotFoundError, UnauthorizedError
from ..models.user import User
from ..models.workspace import Workspace
from ..repositories import user_repository, workspace_repository

logger = logging.getLogger("ledgerlens.deps")

USER_ID_HEADER = "x-ll-user-id"
INTERNAL_SECRET_HEADER = "x-ll-internal-secret"


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
        # Authenticated upstream but the account no longer exists.
        raise UnauthorizedError()
    return user


async def get_current_workspace(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
) -> Workspace:
    """Trusted workspace context for every financial endpoint.

    Day 1: users own exactly one workspace created at signup. The workspace
    id is resolved server-side from authentication — it is NEVER accepted
    from request bodies or query strings, so a browser cannot address another
    tenant's financial data. Workspace membership/roles will extend this
    dependency later without changing any route signature."""
    workspace = await workspace_repository.first_for_owner(db, str(current_user.id))
    if workspace is None:
        raise NotFoundError(message="You don't have an active workspace yet.")
    return workspace
