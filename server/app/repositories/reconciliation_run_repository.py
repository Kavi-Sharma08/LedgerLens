from bson import ObjectId

from ..models.enums import RunStatus
from ..models.reconciliation_run import ReconciliationRun
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "reconciliation_runs"

LIST_SORT = [("startedAt", -1), ("_id", -1)]


async def create_run(db, workspace_id: ObjectId, run: ReconciliationRun) -> ReconciliationRun:
    result = await db[COLLECTION].insert_one(run.to_document())
    run.id = result.inserted_id
    return run


async def get_by_id(db, workspace_id: ObjectId, run_id: str | ObjectId) -> ReconciliationRun:
    from ..core.errors import ReconciliationRunNotFoundError

    try:
        _id = ObjectId(str(run_id))
    except Exception:
        raise ReconciliationRunNotFoundError() from None
    doc = await db[COLLECTION].find_one({"_id": _id, "workspaceId": workspace_id})
    if doc is None:
        raise ReconciliationRunNotFoundError()
    return ReconciliationRun.from_document(doc)


async def mark_running(db, run_id: ObjectId) -> None:
    from datetime import datetime, timezone

    await db[COLLECTION].update_one(
        {"_id": run_id},
        {"$set": {"status": RunStatus.RUNNING.value, "startedAt": datetime.now(timezone.utc)}},
    )


async def complete_run(db, run_id: ObjectId, stats: dict, status: RunStatus, error: str | None = None) -> None:
    from datetime import datetime, timezone

    await db[COLLECTION].update_one(
        {"_id": run_id},
        {
            "$set": {
                "status": status.value,
                "completedAt": datetime.now(timezone.utc),
                **stats,
                "error": error,
            }
        },
    )


async def list_runs(
    db,
    workspace_id: ObjectId,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query = {"workspaceId": workspace_id}
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), LIST_SORT, cast={"startedAt": iso_to_datetime}),
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
        started = doc.get("startedAt")
        return encode_cursor({"startedAt": started.isoformat() if started else "", "_id": str(doc["_id"])})

    next_cursor = _cursor_for(docs[-1]) if has_more and docs else None
    return Page(items=[ReconciliationRun.from_document(d) for d in docs], next_cursor=next_cursor)


async def count_runs(db, workspace_id: ObjectId) -> int:
    return await db[COLLECTION].count_documents({"workspaceId": workspace_id})
