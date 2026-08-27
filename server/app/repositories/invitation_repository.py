from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import AppError
from ..models.enums import InvitationStatus
from ..models.invitation import Invitation

COLLECTION = "invitations"


async def create_invitation(db, invitation: Invitation) -> Invitation:
    """Insert a new invitation. Rejects if a pending invite already exists."""
    try:
        result = await db[COLLECTION].insert_one(invitation.to_document())
    except DuplicateKeyError:
        raise AppError(
            status_code=409,
            code="invitation_already_pending",
            message="An invitation has already been sent to this email for this workspace.",
        ) from None
    invitation.id = result.inserted_id
    return invitation


async def get_pending_invitation(db, workspace_id: ObjectId | str, email: str) -> Invitation | None:
    """Find a pending invitation for a specific workspace and email."""
    doc = await db[COLLECTION].find_one({
        "workspaceId": ObjectId(workspace_id),
        "email": email.lower().strip(),
        "status": InvitationStatus.PENDING.value,
    })
    return Invitation.from_document(doc) if doc else None


async def get_invitation_by_token(db, token_hash: str) -> Invitation | None:
    """Look up an invitation by its hashed token (for acceptance flow)."""
    doc = await db[COLLECTION].find_one({
        "tokenHash": token_hash,
        "status": InvitationStatus.PENDING.value,
    })
    return Invitation.from_document(doc) if doc else None


async def accept_invitation(db, invitation_id: ObjectId | str) -> Invitation:
    """Mark an invitation as accepted."""
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(invitation_id), "status": InvitationStatus.PENDING.value},
        {
            "$set": {
                "status": InvitationStatus.ACCEPTED.value,
                "acceptedAt": datetime.now(timezone.utc),
            }
        },
        return_document=True,
    )
    if doc is None:
        raise AppError(status_code=404, code="invitation_not_found", message="This invitation is no longer valid.")
    return Invitation.from_document(doc)


async def expire_invitation(db, invitation_id: ObjectId | str) -> Invitation:
    """Mark an invitation as expired."""
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(invitation_id)},
        {"$set": {"status": InvitationStatus.EXPIRED.value}},
        return_document=True,
    )
    if doc is None:
        raise AppError(status_code=404, code="invitation_not_found", message="Invitation not found.")
    return Invitation.from_document(doc)


async def list_invitations_for_workspace(db, workspace_id: ObjectId | str) -> list[Invitation]:
    """List all invitations for a workspace, newest first."""
    cursor = db[COLLECTION].find({"workspaceId": ObjectId(workspace_id)}).sort("createdAt", -1)
    return [Invitation.from_document(doc) async for doc in cursor]
