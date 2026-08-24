from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from .enums import SourceStatus, SourceType
from .user import utcnow


@dataclass
class Source:
    """A logical origin of financial records (bank, gateway, ledger...)."""

    workspace_id: ObjectId
    name: str
    type: SourceType
    institution: str | None = None
    account_identifier: str | None = None
    currency: str = "INR"
    status: SourceStatus = SourceStatus.ACTIVE
    metadata: dict = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "name": self.name.strip(),
            "type": self.type.value if isinstance(self.type, SourceType) else self.type,
            "institution": self.institution,
            "accountIdentifier": self.account_identifier,
            "currency": self.currency,
            "status": self.status.value if isinstance(self.status, SourceStatus) else self.status,
            "metadata": self.metadata,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "Source":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            name=doc.get("name", ""),
            type=SourceType(doc.get("type", SourceType.MANUAL.value)),
            institution=doc.get("institution"),
            account_identifier=doc.get("accountIdentifier"),
            currency=doc.get("currency", "INR"),
            status=SourceStatus(doc.get("status", SourceStatus.ACTIVE.value)),
            metadata=doc.get("metadata") or {},
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
