from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import DuplicateSourceError, SourceNotFoundError
from ..models.source import Source
from ..models.enums import SourceStatus, SourceType
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "sources"

# Listing order is stable for cursor pagination.
LIST_SORT = [("createdAt", -1), ("_id", -1)]


async def create_source(db, workspace_id: ObjectId, source: Source) -> Source:
    """The (workspaceId, name) unique index is the concurrency source of truth."""
    try:
        result = await db[COLLECTION].insert_one(source.to_document())
    except DuplicateKeyError:
        raise DuplicateSourceError() from None
    source.id = result.inserted_id
    return source


async def get_by_id(db, workspace_id: ObjectId, source_id: str | ObjectId) -> Source:
    """Workspace-scoped: another tenant's source id behaves as not-found."""
    try:
        _id = ObjectId(str(source_id))
    except Exception:
        raise SourceNotFoundError() from None
    doc = await db[COLLECTION].find_one({"_id": _id, "workspaceId": workspace_id})
    if doc is None:
        raise SourceNotFoundError()
    return Source.from_document(doc)


async def get_by_name(db, workspace_id: ObjectId, name: str) -> Source | None:
    doc = await db[COLLECTION].find_one(
        {"workspaceId": workspace_id, "name": name.strip()}
    )
    return Source.from_document(doc) if doc else None


def list_query(
    workspace_id: ObjectId,
    *,
    source_type: SourceType | None = None,
    status: SourceStatus | None = None,
) -> dict:
    query: dict = {"workspaceId": workspace_id}
    if source_type is not None:
        query["type"] = source_type.value
    if status is not None:
        query["status"] = status.value
    return query


async def list_sources(
    db,
    workspace_id: ObjectId,
    *,
    source_type: SourceType | None = None,
    status: SourceStatus | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    query = list_query(workspace_id, source_type=source_type, status=status)
    page_size = clamp_page_size(limit)
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), LIST_SORT, cast={"createdAt": iso_to_datetime}),
    }
    cursor_obj = (
        db[COLLECTION]
        .find(mongo_filter)
        .sort(LIST_SORT)
        .limit(page_size + 1)
    )
    docs = await cursor_obj.to_list(length=page_size + 1)

    has_more = len(docs) > page_size
    docs = docs[:page_size]
    next_cursor = None
    if has_more and docs:
        last = docs[-1]
        created = last["createdAt"]
        next_cursor = encode_cursor(
            {
                "createdAt": created.isoformat() if hasattr(created, "isoformat") else str(created),
                "_id": str(last["_id"]),
            }
        )
    return Page(items=[Source.from_document(d) for d in docs], next_cursor=next_cursor)


async def count_sources(db, workspace_id: ObjectId) -> int:
    return await db[COLLECTION].count_documents({"workspaceId": workspace_id})
