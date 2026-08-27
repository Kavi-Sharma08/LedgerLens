from datetime import datetime, timedelta, timezone

import re

from bson import ObjectId
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...api.deps import WORKSPACE_ID_HEADER, get_current_user
from ...core.database import get_database
from ...core.errors import AppError, ForbiddenError, NotFoundError
from ...models.enums import InvitationStatus, MembershipStatus, WorkspaceRole
from ...models.invitation import Invitation
from ...models.user import User
from ...models.workspace import Workspace
from ...repositories import invitation_repository as invite_repo
from ...repositories import user_repository
from ...repositories import workspace_repository
from ...repositories import workspace_member_repository as member_repo
from ...schemas.user import (
    WorkspaceCreate,
    WorkspaceMemberPublic,
    WorkspacePublic,
    WorkspaceSettingsUpdate,
)
from ...services.audit_helper import log_audit
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
    request: Request = None,
    db=Depends(get_database),
):
    """The signed-in user's active workspace.

    Resolves from X-LL-Workspace-Id when present (the browser's choice,
    passed through by the Next.js boundary). Falls back to the first
    membership for backward compatibility. Membership is always verified,
    so a forged header is rejected.
    """
    header_ws = (request.headers.get(WORKSPACE_ID_HEADER, "") if request else "").strip()

    if header_ws:
        try:
            ObjectId(header_ws)
        except Exception:
            header_ws = ""
        else:
            member = await member_repo.get_member(db, header_ws, current_user.id)
            if member is None or member.status != MembershipStatus.ACTIVE:
                header_ws = ""
            else:
                workspace = await workspace_repository.get_by_id(db, header_ws)
                if workspace is not None:
                    return to_workspace_public(workspace)

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

    name = payload.name.strip()
    if not name:
        raise AppError(status_code=422, message="Workspace name is required.")

    # Generate unique slug
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

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="workspace_created",
        entity_type="workspace",
        entity_id=str(workspace.id),
        details={"name": name, "slug": slug},
    )

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

    await log_audit(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        action="workspace_updated",
        entity_type="workspace",
        entity_id=str(workspace.id),
        details=updates,
    )

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

    await log_audit(
        db,
        workspace_id=ObjectId(workspace_id),
        user_id=current_user.id,
        action="role_changed",
        entity_type="member",
        entity_id=user_id,
        details={
            "targetUserId": user_id,
            "oldRole": target_member.role.value if target_member else None,
            "newRole": new_role.value,
        },
    )

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

    await log_audit(
        db,
        workspace_id=ObjectId(workspace_id),
        user_id=current_user.id,
        action="member_removed",
        entity_type="member",
        entity_id=user_id,
        details={
            "targetUserId": user_id,
            "role": target.role.value,
            "isSelfRemoval": is_self,
        },
    )

    return {"status": "ok"}


# --- Invitations ---


class InvitationCreate(BaseModel):
    email: str
    role: str = "MEMBER"


@router.get("/{workspace_id}/invitations")
async def list_invitations(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """List all invitations for a workspace. Any member can view."""
    access = await member_repo.has_workspace_access(db, workspace_id, current_user.id)
    if not access:
        raise NotFoundError(message="Workspace not found.")

    invitations = await invite_repo.list_invitations_for_workspace(db, workspace_id)
    results = []
    for inv in invitations:
        invited_by_name = None
        if inv.invited_by:
            inviter = await user_repository.get_by_id(db, inv.invited_by)
            invited_by_name = inviter.name if inviter else None
        results.append({
            "id": str(inv.id),
            "workspaceId": str(inv.workspace_id),
            "email": inv.email,
            "role": inv.role.value,
            "status": inv.status.value,
            "invitedBy": invited_by_name,
            "expiresAt": inv.expires_at.isoformat() if inv.expires_at else None,
            "createdAt": inv.created_at.isoformat() if inv.created_at else None,
        })
    return results


@router.post("/{workspace_id}/invitations", status_code=201)
async def create_invitation(
    workspace_id: str,
    payload: InvitationCreate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_database),
):
    """Send an invitation to join a workspace. Requires invite_members permission (ADMIN+)."""
    perm = await member_repo.has_permission(db, workspace_id, current_user.id, "invite_members")
    if not perm:
        raise ForbiddenError(message="You don't have permission to invite members.")

    email = payload.email.strip().lower()
    if not email:
        raise AppError(status_code=422, message="Email is required.")

    try:
        role = WorkspaceRole(payload.role)
    except ValueError:
        raise AppError(status_code=422, message=f"Invalid role: {payload.role}. Use ADMIN, MEMBER, or VIEWER.")

    if role == WorkspaceRole.OWNER:
        raise AppError(status_code=422, message="Cannot invite someone as Owner.")

    existing_user = await user_repository.get_by_email(db, email)
    if existing_user:
        existing_member = await member_repo.get_member(db, workspace_id, existing_user.id)
        if existing_member and existing_member.status == MembershipStatus.ACTIVE:
            raise AppError(status_code=409, code="already_member", message="This user is already a member of this workspace.")

    existing_invite = await invite_repo.get_pending_invitation(db, workspace_id, email)
    if existing_invite:
        await invite_repo.expire_invitation(db, existing_invite.id)

    import hashlib
    import secrets

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invitation = Invitation(
        workspace_id=ObjectId(workspace_id),
        email=email,
        role=role,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        invited_by=current_user.id,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    invitation = await invite_repo.create_invitation(db, invitation)

    workspace = await workspace_repository.get_by_id(db, workspace_id)

    # Send invitation email via Nodemailer
    try:
        import httpx
        app_url = "http://localhost:3000"
        accept_url = f"{app_url}/accept-invitation/{raw_token}"
        # Fire-and-forget email via the Next.js API
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{app_url}/api/invitations/send-email",
                json={
                    "to": email,
                    "workspaceName": workspace.name,
                    "invitedByName": current_user.name or current_user.email,
                    "acceptUrl": accept_url,
                },
                timeout=10.0,
            )
    except Exception:
        import logging
        logging.getLogger("ledgerlens.invitations").exception("Failed to send invitation email")

    return {
        "id": str(invitation.id),
        "workspaceId": str(invitation.workspace_id),
        "email": invitation.email,
        "role": invitation.role.value,
        "status": invitation.status.value,
        "invitedBy": current_user.name,
        "workspaceName": workspace.name,
        "expiresAt": invitation.expires_at.isoformat() if invitation.expires_at else None,
        "createdAt": invitation.created_at.isoformat() if invitation.created_at else None,
    }
