from bson import ObjectId

from ..models.audit_log import AuditLog
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "audit_logs"

LIST_SORT = [("createdAt", -1), ("_id", -1)]


async def log(
    db,
    workspace_id: ObjectId,
    user_id: ObjectId,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    details: dict | None = None,
) -> AuditLog:
    """Create an immutable audit record. Returns the created entry."""
    entry = AuditLog(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    result = await db[COLLECTION].insert_one(entry.to_document())
    entry.id = result.inserted_id
    return entry


async def list_for_workspace(
    db,
    workspace_id: ObjectId,
    *,
    action: str | None = None,
    user_id: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    """Workspace-scoped audit feed, newest first."""
    page_size = clamp_page_size(limit)
    query: dict = {"workspaceId": workspace_id}
    if action:
        query["action"] = action
    if user_id:
        query["userId"] = ObjectId(user_id)

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
        items=[AuditLog.from_document(d) for d in docs],
        next_cursor=next_cursor,
    )
