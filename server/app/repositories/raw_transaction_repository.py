from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..models.raw_transaction import RawTransaction
from .common import Page, build_filter_from_cursor, clamp_page_size, decode_cursor, encode_cursor

COLLECTION = "raw_transactions"

LIST_SORT = [("ordinal", 1), ("_id", 1)]


async def insert_raw(
    db, workspace_id: ObjectId, raw: RawTransaction
) -> tuple[RawTransaction, bool]:
    """Insert evidence row. Returns (raw, inserted).

    The (workspaceId, sourceId, recordHash) unique index guarantees replayed
    files can never duplicate evidence; a collision returns the existing row
    with inserted=False so the caller skips canonical creation idempotently."""
    try:
        result = await db[COLLECTION].insert_one(raw.to_document())
    except DuplicateKeyError:
        existing = await db[COLLECTION].find_one(
            {
                "workspaceId": workspace_id,
                "sourceId": raw.source_id,
                "recordHash": raw.record_hash,
            }
        )
        if existing is None:
            # Should not happen, but never fail ingestion on bookkeeping.
            return raw, False
        return RawTransaction.from_document(existing), False
    raw.id = result.inserted_id
    return raw, True


async def get_by_id(db, workspace_id: ObjectId, raw_id: ObjectId) -> RawTransaction | None:
    doc = await db[COLLECTION].find_one({"_id": raw_id, "workspaceId": workspace_id})
    return RawTransaction.from_document(doc) if doc else None


async def list_for_file(
    db,
    workspace_id: ObjectId,
    source_file_id: ObjectId,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query = {"workspaceId": workspace_id, "sourceFileId": source_file_id}
    mongo_filter = {**query, **build_filter_from_cursor(decode_cursor(cursor), LIST_SORT)}
    cursor_obj = (
        db[COLLECTION]
        .find(mongo_filter)
        .sort(LIST_SORT)
        .limit(page_size + 1)
    )
    docs = await cursor_obj.to_list(length=page_size + 1)
    has_more = len(docs) > page_size
    docs = docs[:page_size]
    next_cursor = (
        encode_cursor({"ordinal": docs[-1]["ordinal"], "_id": str(docs[-1]["_id"])})
        if has_more and docs
        else None
    )
    return Page(items=[RawTransaction.from_document(d) for d in docs], next_cursor=next_cursor)


async def delete_by_source(db, workspace_id: ObjectId, source_id: ObjectId) -> int:
    """Delete all raw transactions for a given source. Returns count deleted."""
    result = await db[COLLECTION].delete_many(
        {"workspaceId": workspace_id, "sourceId": source_id}
    )
    return result.deleted_count
