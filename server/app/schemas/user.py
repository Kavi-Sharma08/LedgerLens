from pydantic import BaseModel


class UserPublic(BaseModel):
    """Safe-to-expose user representation (never includes passwordHash)."""

    id: str
    name: str
    email: str
    avatar: str | None = None


class WorkspacePublic(BaseModel):
    id: str
    name: str
    slug: str


class WorkspaceMemberPublic(BaseModel):
    id: str
    workspaceId: str
    userId: str
    userName: str | None = None
    userEmail: str | None = None
    role: str
    status: str
    joinedAt: str | None = None
    createdAt: str | None = None


class WorkspaceCreate(BaseModel):
    name: str
    type: str | None = None  # PERSONAL | BUSINESS


class MemberRoleUpdate(BaseModel):
    role: str  # ADMIN | MEMBER | VIEWER


class WorkspaceSettingsUpdate(BaseModel):
    name: str | None = None
