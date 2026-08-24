"""Shared API schemas."""

from pydantic import BaseModel


class PageMeta(BaseModel):
    limit: int
    nextCursor: str | None = None


def paginated(items: list, limit: int, next_cursor: str | None) -> dict:
    """Envelope for cursor-paginated list endpoints."""
    return {
        "items": items,
        "page": {"limit": limit, "nextCursor": next_cursor},
    }
