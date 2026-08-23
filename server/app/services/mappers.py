"""Mapping helpers: internal models -> public API payloads."""

from ..models.user import User
from ..models.workspace import Workspace
from ..schemas.user import UserPublic, WorkspacePublic


def to_user_public(user: User) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        name=user.name,
        email=user.email,
        avatar=user.avatar,
    )


def to_workspace_public(workspace: Workspace | None) -> WorkspacePublic | None:
    if workspace is None or workspace.id is None:
        return None
    return WorkspacePublic(id=str(workspace.id), name=workspace.name, slug=workspace.slug)
