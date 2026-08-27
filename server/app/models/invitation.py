from dataclasses import dataclass
from datetime import datetime, timezone
from bson import ObjectId
from .enums import InvitationStatus, WorkspaceRole


@dataclass
class Invitation:
    workspace_id: ObjectId
    email: str
    role: WorkspaceRole
    token_hash: str  # SHA-256 hash of the raw token
    status: InvitationStatus = InvitationStatus.PENDING
    invited_by: ObjectId | None = None
    expires_at: datetime | None = None
    accepted_at: datetime | None = None
    created_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "workspaceId": self.workspace_id,
            "email": self.email.lower().strip(),
            "role": self.role.value if isinstance(self.role, WorkspaceRole) else self.role,
            "tokenHash": self.token_hash,
            "status": self.status.value if isinstance(self.status, InvitationStatus) else self.status,
            "invitedBy": self.invited_by,
            "expiresAt": self.expires_at,
            "acceptedAt": self.accepted_at,
            "createdAt": self.created_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "Invitation":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            email=doc["email"],
            token_hash=doc["tokenHash"],
            status=InvitationStatus(doc.get("status", InvitationStatus.PENDING.value)),
            role=WorkspaceRole(doc.get("role", WorkspaceRole.MEMBER.value)),
            invited_by=doc.get("invitedBy"),
            expires_at=doc.get("expiresAt"),
            accepted_at=doc.get("acceptedAt"),
            created_at=doc.get("createdAt"),
        )
