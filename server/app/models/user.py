from dataclasses import dataclass
from datetime import datetime, timezone

from bson import ObjectId


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    """MongoDB document shape for users.

    The users collection is managed by the Auth.js MongoDB adapter on the
    Next.js side, so documents follow the adapter shape plus our extensions:

    {
        _id,
        name,
        email,
        emailVerified,   # Auth.js adapter
        image,           # avatar URL (adapter standard; falls back to `avatar`)
        passwordHash,    # absent for Google-only accounts
        avatar,          # legacy alias of image
        createdAt,
        updatedAt
    }
    """

    name: str
    email: str
    password_hash: str | None = None  # None for OAuth-only accounts
    avatar: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "name": self.name,
            "email": self.email.lower(),
            "emailVerified": None,
            "image": self.avatar,
            "passwordHash": self.password_hash,
            "avatar": self.avatar,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "User":
        return cls(
            id=doc["_id"],
            name=doc.get("name", ""),
            email=doc.get("email", ""),
            password_hash=doc.get("passwordHash"),
            avatar=doc.get("image") or doc.get("avatar"),
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
