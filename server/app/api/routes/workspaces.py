from bson import ObjectId
from fastapi import APIRouter, Depends

from ...api.deps import get_current_membership, get_current_user, require_permission
from ...core.database import get_database
from ...core.errors import AppError, ForbiddenError, NotFoundError
from ...models.enums import WorkspaceRole
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import workspace_repository
from ...repositories import workspace_member_repository as member_repo
from ...schemas.user import (
    WorkspaceCreate,
    WorkspaceMemberPublic,
    WorkspacePublic,
    WorkspaceSettingsUpdate,
)
from ...services.mappers import to_workspace_public

router = APIRouter()


@router.get("", response_model=list[WorkspacePublic])
async def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """List every workspace the signed-in user belongs to."""
    memberships = await member_repo.get_workspaces_for_user(db, current_user.id)
    results = []
    for m in memberships:
        try:
            ws = await workspace_repository.get_by_id(db, m["workspaceId"])
            results.append(to_workspace_public(ws))
        except NotFoundError:
            continue
    return results


@router.get("/current", response_model=WorkspacePublic)
async def read_current_workspace(
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """The signed-in user's active workspace (resolved from X-LL-Workspace-Id)."""
    from ...api.deps import get_current_workspace as _get_ws
    from starlette.requests import Request as StarletteRequest
    # This endpoint is called server-side by Next.js without X-LL-Workspace-Id.
    # Fall back to membership-based resolution for backward compat.
    memberships = await member_repo.get_workspaces_for_user(db, current_user.id)
    if not memberships:
        raise NotFoundError(message="You don't have an active workspace yet.")
    workspace_id = memberships[0]["workspaceId"]
    workspace = await workspace_repository.get_by_id(db, workspace_id)
    return to_workspace_public(workspace)


@router.post("", response_model=WorkspacePublic, status_code=201)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Create a new workspace. The creator becomes OWNER."""
    from ...models.workspace import Workspace as WorkspaceModel
    from datetime import datetime, timezone

    name = payload.name.strip()
    if not name:
        raise AppError(status_code=422, message="Workspace name is required.")

    # Generate unique slug
    base_slug = WorkspaceModel(
        name=name, slug="", owner_id=current_user.id
    ).slug if hasattr(WorkspaceModel, 'slug') else ""

    import re
    slug_base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:48] or "workspace"
    slug = slug_base
    suffix = 1
    while await workspace_repository.slug_exists(db, slug):
        suffix += 1
        slug = f"{slug_base}-{suffix}"

    now = datetime.now(timezone.utc)
    workspace = WorkspaceModel(
        name=name,
        slug=slug,
        owner_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    workspace = await workspace_repository.create_workspace(db, workspace)

    # Create OWNER membership
    from ...models.workspace_member import WorkspaceMember
    from ...models.enums import MembershipStatus
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role=WorkspaceRole.OWNER,
        status=MembershipStatus.ACTIVE,
        joined_at=now,
        created_at=now,
        updated_at=now,
    )
    await member_repo.create_member(db, member)

    return to_workspace_public(workspace)


@router.patch("/{workspace_id}", response_model=WorkspacePublic)
async def update_workspace_settings(
    workspace_id: str,
    payload: WorkspaceSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Update workspace settings (OWNER only)."""
    member = await member_repo.get_member(db, workspace_id, current_user.id)
    if member is None:
        raise NotFoundError(message="You don't have access to this workspace.")
    if member.role != WorkspaceRole.OWNER:
        raise ForbiddenError(message="Only the workspace owner can change workspace settings.")

    updates = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise AppError(status_code=422, message="Workspace name cannot be empty.")
        updates["name"] = name

    if not updates:
        return to_workspace_public(await workspace_repository.get_by_id(db, workspace_id))

    workspace = await workspace_repository.update_workspace(db, workspace_id, updates)
    return to_workspace_public(workspace)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberPublic])
async def list_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """List members of a workspace. Any member can view the member list."""
    # Verify the requester has access
    access = await member_repo.has_workspace_access(db, workspace_id, current_user.id)
    if not access:
        raise NotFoundError(message="Workspace not found.")

    members = await member_repo.list_members_for_workspace(db, workspace_id)

    # Enrich with user names/emails
    from ...repositories import user_repository
    results = []
    for m in members:
        user = await user_repository.get_by_id(db, m.user_id)
        results.append(WorkspaceMemberPublic(
            id=str(m.id),
            workspaceId=str(m.workspace_id),
            userId=str(m.user_id),
            userName=user.name if user else None,
            userEmail=user.email if user else None,
            role=m.role.value,
            status=m.status.value,
            joinedAt=m.joined_at.isoformat() if m.joined_at else None,
            createdAt=m.created_at.isoformat() if m.created_at else None,
        ))
    return results


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Change a member's role. Requires MANAGE_MEMBERS permission (ADMIN+)."""
    perm = await member_repo.has_permission(db, workspace_id, current_user.id, "manage_members")
    if not perm:
        raise ForbiddenError(message="You don't have permission to manage members.")

    new_role_str = payload.get("role", "")
    try:
        new_role = WorkspaceRole(new_role_str)
    except ValueError:
        raise AppError(status_code=422, message=f"Invalid role: {new_role_str}. Use OWNER, ADMIN, MEMBER, or VIEWER.")

    if new_role == WorkspaceRole.OWNER:
        raise AppError(status_code=422, message="Ownership cannot be transferred via role change.")

    # Cannot downgrade an OWNER
    target_member = await member_repo.get_member(db, workspace_id, user_id)
    if target_member and target_member.role == WorkspaceRole.OWNER:
        raise ForbiddenError(message="Cannot change the role of the workspace owner.")

    updated = await member_repo.update_member_role(db, workspace_id, user_id, new_role)
    return {"status": "ok", "role": updated.role.value}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Remove a member from the workspace. Requires MANAGE_MEMBERS (ADMIN+).
    Members can remove themselves (leave workspace)."""
    is_self = str(current_user.id) == user_id
    if not is_self:
        perm = await member_repo.has_permission(db, workspace_id, current_user.id, "manage_members")
        if not perm:
            raise ForbiddenError(message="You don't have permission to remove members.")

    target = await member_repo.get_member(db, workspace_id, user_id)
    if target is None:
        raise NotFoundError(message="That user isn't a member of this workspace.")
    if target.role == WorkspaceRole.OWNER and not is_self:
        raise ForbiddenError(message="Cannot remove the workspace owner.")

    await member_repo.remove_member(db, workspace_id, user_id)
    return {"status": "ok"}
