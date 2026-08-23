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
