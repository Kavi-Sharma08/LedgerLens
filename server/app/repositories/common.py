"""Shared repository utilities: keyset (cursor) pagination.

Keyset pagination is used instead of skip/limit because workspaces will grow
to millions of transactions; OFFSET scans degrade linearly while a seek on
the sort key does not. Cursors are opaque to clients."""

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from bson import ObjectId

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50


def utc_isoformat(value) -> str | None:
    """Serialize a datetime as an ISO string with an explicit UTC offset.

    PyMongo decodes BSON dates as *naive* UTC datetimes, so `datetime.isoformat()`
    emits no offset (e.g. "2026-08-27T08:13:11.397000"). Clients then can't tell
    the value is UTC and may misread it as local time. This always emits the
    "+00:00" suffix so the instant is unambiguous.
    """
    if value is None:
        return None
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.isoformat()


class InvalidCursorError(ValueError):
    pass


@dataclass
class Page:
    items: list
    next_cursor: str | None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


def encode_cursor(sort_values: dict) -> str:
    payload = json.dumps(sort_values, default=str).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_cursor(cursor: str | None) -> dict | None:
    if not cursor:
        return None
    try:
        payload = base64.urlsafe_b64decode(cursor.encode("ascii"))
        data = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise InvalidCursorError("Pagination cursor is invalid.") from exc
    if not isinstance(data, dict):
        raise InvalidCursorError("Pagination cursor is invalid.")
    return data


def iso_to_datetime(value) -> datetime | None:
    """Cursor payloads are JSON, so datetimes travel as ISO strings and must
    be converted back before they can be compared with stored BSON dates."""
    if value is None or isinstance(value, datetime):
        return value
    text = str(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidCursorError("Pagination cursor is invalid.") from exc


def build_filter_from_cursor(
    cursor_data: dict | None,
    sort_spec: list[tuple[str, int]],
    cast: dict | None = None,
) -> dict:
    """Mongo range predicate implementing keyset continuation for the given
    multi-field sort (last field must be `_id` as the unique tiebreaker).

    For sort [(a, -1), (_id, -1)] the predicate is:
        $or: [{a: {$lt: va}}, {a: va, _id: {$lt: vid}}]

    `cast` maps field names to converters that restore native types from the
    JSON cursor payload (e.g. ISO strings -> datetime).
    """
    if not cursor_data:
        return {}
    cast = cast or {}
    or_clauses = []
    for index in range(len(sort_spec)):
        field_name, direction = sort_spec[index]
        equality = {}
        for prior_name, _ in sort_spec[:index]:
            prior_value = cursor_data.get(prior_name)
            if prior_name in cast:
                prior_value = cast[prior_name](prior_value)
            equality[prior_name] = prior_value
        comparator = "$lt" if direction == -1 else "$gt"
        value = cursor_data.get(field_name)
        if field_name == "_id":
            try:
                value = ObjectId(value)
            except Exception as exc:
                raise InvalidCursorError("Pagination cursor is invalid.") from exc
        elif field_name in cast:
            value = cast[field_name](value)
            if value is None:
                # Cursor carried no usable value for this key; the _id clause
                # alone still continues safely.
                continue
        or_clauses.append({**equality, field_name: {comparator: value}})
    if not or_clauses:
        raise InvalidCursorError("Pagination cursor is invalid.")
    return {"$or": or_clauses} if len(or_clauses) > 1 else or_clauses[0]


def clamp_page_size(limit: int | None) -> int:
    if limit is None or limit <= 0:
        return DEFAULT_PAGE_SIZE
    return min(limit, MAX_PAGE_SIZE)
