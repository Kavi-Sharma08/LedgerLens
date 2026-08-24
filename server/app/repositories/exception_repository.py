from bson import ObjectId

from ..models.enums import ExceptionStatus
from ..models.reconciliation_exception import ReconciliationException
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "exceptions"

LIST_SORT = [("createdAt", -1), ("_id", -1)]


async def insert_exceptions(db, exceptions: list[ReconciliationException]) -> int:
    if not exceptions:
        return 0
    result = await db[COLLECTION].insert_many([e.to_document() for e in exceptions])
    for doc_id, exc in zip(result.inserted_ids, exceptions):
        exc.id = doc_id
    return len(result.inserted_ids)


async def list_for_run(
    db,
    workspace_id: ObjectId,
    run_id: ObjectId,
    *,
    status: ExceptionStatus | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query: dict = {"workspaceId": workspace_id, "reconciliationRunId": run_id}
    if status is not None:
        query["status"] = status.value
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

    def _cursor_for(doc):
        created = doc.get("createdAt")
        return encode_cursor({"createdAt": created.isoformat() if created else "", "_id": str(doc["_id"])})

    next_cursor = _cursor_for(docs[-1]) if has_more and docs else None
    return Page(
        items=[ReconciliationException.from_document(d) for d in docs],
        next_cursor=next_cursor,
    )


async def list_for_workspace(
    db,
    workspace_id: ObjectId,
    *,
    status: ExceptionStatus | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    """Workspace-wide exception feed (the Exceptions screen)."""
    page_size = clamp_page_size(limit)
    query: dict = {"workspaceId": workspace_id}
    if status is not None:
        query["status"] = status.value
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), LIST_SORT, cast={"createdAt": iso_to_datetime}),
    }
    cursor_obj = db[COLLECTION].find(mongo_filter).sort(LIST_SORT).limit(page_size + 1)
    docs = await cursor_obj.to_list(length=page_size + 1)
    has_more = len(docs) > page_size
    docs = docs[:page_size]

    def _cursor_for(doc):
        created = doc.get("createdAt")
        return encode_cursor({"createdAt": created.isoformat() if created else "", "_id": str(doc["_id"])})

    next_cursor = _cursor_for(docs[-1]) if has_more and docs else None
    return Page(
        items=[ReconciliationException.from_document(d) for d in docs],
        next_cursor=next_cursor,
    )


async def count_open(db, workspace_id: ObjectId) -> int:
    return await db[COLLECTION].count_documents(
        {"workspaceId": workspace_id, "status": ExceptionStatus.OPEN.value}
    )


async def list_open(db, workspace_id: ObjectId, *, limit: int | None = None, cursor: str | None = None) -> Page:
    return await list_for_workspace(
        db, workspace_id, status=ExceptionStatus.OPEN, limit=limit, cursor=cursor
    )
