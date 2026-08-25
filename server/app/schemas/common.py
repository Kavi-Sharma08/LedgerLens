"""Shared API schemas."""

from pydantic import BaseModel


class PageMeta(BaseModel):
    limit: int
    nextCursor: str | None = None


def paginated(items: list, limit: int, next_cursor: str | None) -> dict:
    """Envelope for cursor-paginated list endpoints.

    The frontend reads ``items`` and ``nextCursor`` at the top level, so
    nextCursor is surfaced directly rather than nested inside ``page``.
    """
    return {
        "items": items,
        "page": {"limit": limit, "nextCursor": next_cursor},
        "nextCursor": next_cursor,
    }
