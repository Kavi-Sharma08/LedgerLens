from dataclasses import dataclass
from datetime import datetime

from bson import ObjectId

from .enums import MembershipStatus, WorkspaceRole
from .user import utcnow


@dataclass
class WorkspaceMember:
    """Membership relationship between a user and a workspace.

    One workspace → many members.
    One user → many workspaces.

    Conceptual shape in MongoDB:
        {
            _id,
            workspaceId,
            userId,
            role,          # OWNER | ADMIN | MEMBER | VIEWER
            status,        # ACTIVE | PENDING
            joinedAt,
            createdAt,
            updatedAt
        }
    """

    workspace_id: ObjectId
    user_id: ObjectId
    role: WorkspaceRole = WorkspaceRole.MEMBER
    status: MembershipStatus = MembershipStatus.ACTIVE
    joined_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "userId": self.user_id,
            "role": self.role.value if isinstance(self.role, WorkspaceRole) else self.role,
            "status": self.status.value if isinstance(self.status, MembershipStatus) else self.status,
            "joinedAt": self.joined_at or now,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "WorkspaceMember":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            user_id=doc["userId"],
            role=WorkspaceRole(doc.get("role", WorkspaceRole.MEMBER.value)),
            status=MembershipStatus(doc.get("status", MembershipStatus.ACTIVE.value)),
            joined_at=doc.get("joinedAt"),
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
