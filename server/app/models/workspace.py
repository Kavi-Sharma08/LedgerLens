from dataclasses import dataclass
from datetime import datetime

from bson import ObjectId

from .user import utcnow


@dataclass
class Workspace:
    """MongoDB document shape for workspaces.

    {
        _id,
        name,
        slug,
        ownerId,
        createdAt,
        updatedAt
    }

    Conceptual relationship (expanded into WorkspaceMember/roles in later days):
        User ──owns──> Workspace
    """

    name: str
    slug: str
    owner_id: ObjectId
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "name": self.name,
            "slug": self.slug,
            "ownerId": self.owner_id,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "Workspace":
        return cls(
            id=doc["_id"],
            name=doc.get("name", ""),
            slug=doc.get("slug", ""),
            owner_id=doc.get("ownerId"),
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
