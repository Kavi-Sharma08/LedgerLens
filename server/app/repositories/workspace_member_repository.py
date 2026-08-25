from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import AppError
from ..models.enums import MembershipStatus, WorkspaceRole
from ..models.workspace_member import WorkspaceMember

COLLECTION = "workspace_members"


async def create_member(db, member: WorkspaceMember) -> WorkspaceMember:
    """Insert a workspace membership record."""
    try:
        result = await db[COLLECTION].insert_one(member.to_document())
    except DuplicateKeyError:
        raise AppError(
            status_code=409,
            code="already_member",
            message="This user is already a member of this workspace.",
        ) from None
    member.id = result.inserted_id
    return member


async def get_member(
    db, workspace_id: ObjectId | str, user_id: ObjectId | str
) -> WorkspaceMember | None:
    """Single membership lookup (workspace + user)."""
    doc = await db[COLLECTION].find_one(
        {"workspaceId": ObjectId(workspace_id), "userId": ObjectId(user_id)}
    )
    return WorkspaceMember.from_document(doc) if doc else None


async def get_member_or_none(
    db, workspace_id: ObjectId | str, user_id: ObjectId | str
) -> WorkspaceMember | None:
    return await get_member(db, workspace_id, user_id)


async def list_members_for_workspace(db, workspace_id: ObjectId | str) -> list[WorkspaceMember]:
    """All members of a workspace (any status), ordered by role hierarchy then name."""
    role_order = {WorkspaceRole.OWNER: 0, WorkspaceRole.ADMIN: 1, WorkspaceRole.MEMBER: 2, WorkspaceRole.VIEWER: 3}
    cursor = db[COLLECTION].find({"workspaceId": ObjectId(workspace_id)})
    members = [WorkspaceMember.from_document(doc) async for doc in cursor]
    members.sort(key=lambda m: (role_order.get(m.role, 99), str(m.user_id)))
    return members


async def get_workspaces_for_user(db, user_id: ObjectId | str) -> list[dict]:
    """Return every workspace a user belongs to (ACTIVE membership only), with role.

    Returns a list of dicts: {workspaceId, role, status, joinedAt}.
    Caller fetches workspace documents separately.
    """
    cursor = db[COLLECTION].find(
        {"userId": ObjectId(user_id), "status": MembershipStatus.ACTIVE.value}
    ).sort("joinedAt", 1)
    return [doc async for doc in cursor]


async def update_member_role(
    db,
    workspace_id: ObjectId | str,
    user_id: ObjectId | str,
    new_role: WorkspaceRole,
) -> WorkspaceMember:
    """Change a member's role. Returns the updated member."""
    from datetime import datetime, timezone

    result = await db[COLLECTION].find_one_and_update(
        {"workspaceId": ObjectId(workspace_id), "userId": ObjectId(user_id)},
        {"$set": {"role": new_role.value, "updatedAt": datetime.now(timezone.utc)}},
        return_document=True,
    )
    if result is None:
        raise AppError(status_code=404, code="member_not_found", message="That user isn't a member of this workspace.")
    return WorkspaceMember.from_document(result)


async def remove_member(db, workspace_id: ObjectId | str, user_id: ObjectId | str) -> bool:
    """Remove a member from a workspace. Returns True if a member was removed."""
    result = await db[COLLECTION].delete_one(
        {"workspaceId": ObjectId(workspace_id), "userId": ObjectId(user_id)}
    )
    return result.deleted_count > 0


async def has_permission(db, workspace_id: ObjectId | str, user_id: ObjectId | str, permission: str) -> bool:
    """Check whether the user has the named permission in this workspace."""
    from ..models.enums import user_has_permission

    member = await get_member(db, workspace_id, user_id)
    if member is None or member.status != MembershipStatus.ACTIVE:
        return False
    return user_has_permission(member.role, permission)


async def has_workspace_access(db, workspace_id: ObjectId | str, user_id: ObjectId | str) -> bool:
    """Quick check: does this user have ANY active membership in the workspace?"""
    doc = await db[COLLECTION].find_one(
        {"workspaceId": ObjectId(workspace_id), "userId": ObjectId(user_id), "status": MembershipStatus.ACTIVE.value},
        projection={"_id": 1},
    )
    return doc is not None
