from dataclasses import dataclass
from datetime import datetime

from bson import ObjectId

from .user import utcnow


# Named audit actions — use these constants for consistency across the codebase.
WORKSPACE_CREATED = "workspace_created"
MEMBER_INVITED = "member_invited"
MEMBER_ACCEPTED = "member_accepted"
ROLE_CHANGED = "role_changed"
MEMBER_REMOVED = "member_removed"
SOURCE_CREATED = "source_created"
FILE_UPLOADED = "file_uploaded"
RECONCILIATION_STARTED = "reconciliation_started"
RECONCILIATION_COMPLETED = "reconciliation_completed"
MATCH_APPROVED = "match_approved"
MATCH_REJECTED = "match_rejected"
EXCEPTION_ASSIGNED = "exception_assigned"
EXCEPTION_STATUS_CHANGED = "exception_status_changed"
EXCEPTION_NOTE_ADDED = "exception_note_added"
PASSWORD_SET = "password_set"


@dataclass
class AuditLog:
    """Immutable record of a significant workspace action.

    Conceptual shape in MongoDB:
        {
            _id,
            workspaceId,
            userId,
            action,
            entityType,   # "workspace" | "source" | "file" | "match" | "exception" | ...
            entityId,
            details,      # arbitrary context dict
            createdAt     # immutable — set once at creation
        }
    """

    workspace_id: ObjectId
    user_id: ObjectId
    action: str
    entity_type: str = ""
    entity_id: str = ""
    details: dict | None = None
    created_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "userId": self.user_id,
            "action": self.action,
            "entityType": self.entity_type,
            "entityId": self.entity_id,
            "details": self.details or {},
            "createdAt": self.created_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "AuditLog":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            user_id=doc["userId"],
            action=doc.get("action", ""),
            entity_type=doc.get("entityType", ""),
            entity_id=doc.get("entityId", ""),
            details=doc.get("details") or {},
            created_at=doc.get("createdAt"),
        )
