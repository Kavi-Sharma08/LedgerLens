from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import DuplicateFileError, SourceFileNotFoundError
from ..models.enums import FileStatus
from ..models.source_file import SourceFile
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "source_files"

LIST_SORT = [("uploadedAt", -1), ("_id", -1)]


async def create_file(db, workspace_id: ObjectId, source_file: SourceFile) -> SourceFile:
    """The (workspaceId, sourceId, checksum) unique index makes duplicate
    imports structurally impossible; collisions raise DuplicateFileError."""
    try:
        result = await db[COLLECTION].insert_one(source_file.to_document())
    except DuplicateKeyError:
        raise DuplicateFileError() from None
    source_file.id = result.inserted_id
    return source_file


async def find_by_checksum(
    db, workspace_id: ObjectId, source_id: ObjectId, checksum: str
) -> SourceFile | None:
    doc = await db[COLLECTION].find_one(
        {
            "workspaceId": workspace_id,
            "sourceId": source_id,
            "checksum": checksum,
        }
    )
    return SourceFile.from_document(doc) if doc else None


async def get_by_id(db, workspace_id: ObjectId, file_id: str | ObjectId) -> SourceFile:
    try:
        _id = ObjectId(str(file_id))
    except Exception:
        raise SourceFileNotFoundError() from None
    doc = await db[COLLECTION].find_one({"_id": _id, "workspaceId": workspace_id})
    if doc is None:
        raise SourceFileNotFoundError()
    return SourceFile.from_document(doc)


async def list_for_source(
    db,
    workspace_id: ObjectId,
    source_id: ObjectId,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query = {"workspaceId": workspace_id, "sourceId": source_id}
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), LIST_SORT, cast={"uploadedAt": iso_to_datetime}),
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
    next_cursor = (
        encode_cursor(
            {
                "uploadedAt": docs[-1]["uploadedAt"].isoformat()
                if hasattr(docs[-1]["uploadedAt"], "isoformat")
                else str(docs[-1]["uploadedAt"]),
                "_id": str(docs[-1]["_id"]),
            }
        )
        if has_more and docs
        else None
    )
    return Page(items=[SourceFile.from_document(d) for d in docs], next_cursor=next_cursor)


async def update_processing_result(
    db,
    workspace_id: ObjectId,
    file_id: ObjectId,
    *,
    status: FileStatus,
    transaction_count: int,
    skipped_duplicate_count: int,
    error_count: int,
    error: str | None = None,
) -> None:
    await db[COLLECTION].update_one(
        {"_id": file_id, "workspaceId": workspace_id},
        {
            "$set": {
                "status": status.value,
                "processedAt": datetime.now(timezone.utc),
                "transactionCount": transaction_count,
                "skippedDuplicateCount": skipped_duplicate_count,
                "errorCount": error_count,
                "error": error,
            }
        },
    )


async def delete_by_source(db, workspace_id: ObjectId, source_id: ObjectId) -> int:
    """Delete all source files for a given source. Returns count deleted."""
    result = await db[COLLECTION].delete_many(
        {"workspaceId": workspace_id, "sourceId": source_id}
    )
    return result.deleted_count
