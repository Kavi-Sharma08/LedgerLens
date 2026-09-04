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


async def get_by_id(db, workspace_id: ObjectId, exception_id: ObjectId) -> ReconciliationException | None:
    """Fetch a single exception by id, workspace-scoped."""
    doc = await db[COLLECTION].find_one(
        {"_id": exception_id, "workspaceId": workspace_id}
    )
    return ReconciliationException.from_document(doc) if doc else None


async def assign_exception(
    db, workspace_id: ObjectId, exception_id: ObjectId, assigned_to: ObjectId
) -> ReconciliationException | None:
    """Assign an exception to a team member."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": exception_id, "workspaceId": workspace_id},
        {
            "$set": {
                "assignedTo": assigned_to,
                "assignedAt": now,
                "updatedAt": now,
            }
        },
        return_document=True,
    )
    return ReconciliationException.from_document(doc) if doc else None


async def update_status(
    db,
    workspace_id: ObjectId,
    exception_id: ObjectId,
    status: ExceptionStatus,
    user_id: ObjectId | None = None,
) -> ReconciliationException | None:
    """Change the status of an exception (OPEN -> INVESTIGATING -> RESOLVED/DISMISSED)."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    update_fields = {"status": status.value, "updatedAt": now}

    if status in (ExceptionStatus.RESOLVED, ExceptionStatus.DISMISSED):
        update_fields["resolvedBy"] = user_id
        update_fields["resolvedAt"] = now

    doc = await db[COLLECTION].find_one_and_update(
        {"_id": exception_id, "workspaceId": workspace_id},
        {"$set": update_fields},
        return_document=True,
    )
    return ReconciliationException.from_document(doc) if doc else None


async def add_note(
    db,
    workspace_id: ObjectId,
    exception_id: ObjectId,
    user_id: ObjectId,
    text: str,
    created_by: str | None = None,
) -> dict | None:
    """Append an investigation note to an exception and return the created note."""
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    note = {
        "id": uuid.uuid4().hex,
        "userId": str(user_id),
        "createdBy": created_by,
        "text": text,
        "createdAt": now.isoformat(),
        "updatedAt": None,
    }
    doc = await db[COLLECTION].find_one_and_update(
        {"_id": exception_id, "workspaceId": workspace_id},
        {
            "$push": {"notes": note},
            "$set": {"updatedAt": now},
        },
        return_document=True,
    )
    if doc is None:
        return None
    return note


async def update_note(
    db,
    workspace_id: ObjectId,
    exception_id: ObjectId,
    note_id: str,
    text: str,
) -> dict | None:
    """Edit an investigation note's content; return the updated note or None."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one(
        {"_id": exception_id, "workspaceId": workspace_id}
    )
    if doc is None or not doc.get("notes"):
        return None

    notes = list(doc["notes"])
    updated = None
    for i, note in enumerate(notes):
        if str(note.get("id")) == note_id:
            notes[i] = {**note, "text": text, "updatedAt": now.isoformat()}
            updated = notes[i]
            break
    if updated is None:
        return None

    await db[COLLECTION].update_one(
        {"_id": exception_id},
        {"$set": {"notes": notes, "updatedAt": now}},
    )
    return updated


async def delete_note(
    db,
    workspace_id: ObjectId,
    exception_id: ObjectId,
    note_id: str,
) -> dict | None:
    """Delete an investigation note; return the removed note or None if absent."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    doc = await db[COLLECTION].find_one(
        {"_id": exception_id, "workspaceId": workspace_id}
    )
    if doc is None or not doc.get("notes"):
        return None

    notes = list(doc["notes"])
    remaining = [n for n in notes if str(n.get("id")) != note_id]
    removed = next((n for n in notes if str(n.get("id")) == note_id), None)
    if removed is None:
        return None

    await db[COLLECTION].update_one(
        {"_id": exception_id},
        {"$set": {"notes": remaining, "updatedAt": now}},
    )
    return removed
