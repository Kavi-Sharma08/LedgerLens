from bson import ObjectId

from ..models.match import Match
from ..models.match_candidate import MatchCandidate
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

CANDIDATE_COLLECTION = "match_candidates"
MATCH_COLLECTION = "matches"

MATCH_SORT = [("createdAt", -1), ("_id", -1)]


async def insert_candidate(db, candidate: MatchCandidate) -> ObjectId:
    result = await db[CANDIDATE_COLLECTION].insert_one(candidate.to_document())
    return result.inserted_id


async def insert_candidates(db, candidates: list[MatchCandidate]) -> int:
    if not candidates:
        return 0
    result = await db[CANDIDATE_COLLECTION].insert_many(
        [c.to_document() for c in candidates]
    )
    return len(result.inserted_ids)


async def list_matches_for_run(
    db,
    workspace_id: ObjectId,
    run_id: ObjectId,
    *,
    statuses: list[str] | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query: dict = {"workspaceId": workspace_id, "reconciliationRunId": run_id}
    if statuses:
        query["status"] = {"$in": statuses}
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), MATCH_SORT, cast={"createdAt": iso_to_datetime}),
    }
    cursor_obj = (
        db[MATCH_COLLECTION]
        .find(mongo_filter)
        .sort(MATCH_SORT)
        .limit(page_size + 1)
    )
    docs = await cursor_obj.to_list(length=page_size + 1)
    has_more = len(docs) > page_size
    docs = docs[:page_size]

    def _cursor_for(doc):
        created = doc.get("createdAt")
        return encode_cursor({"createdAt": created.isoformat() if created else "", "_id": str(doc["_id"])})

    next_cursor = _cursor_for(docs[-1]) if has_more and docs else None
    return Page(items=[Match.from_document(d) for d in docs], next_cursor=next_cursor)


async def list_for_transaction(
    db,
    workspace_id: ObjectId,
    transaction_id: ObjectId,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    """Matches whose group involves the given transaction. This is the read
    model behind per-transaction evidence in the UI."""
    page_size = clamp_page_size(limit)
    query = {"workspaceId": workspace_id, "transactionIds": transaction_id}
    mongo_filter = {
        **query,
        **build_filter_from_cursor(decode_cursor(cursor), MATCH_SORT, cast={"createdAt": iso_to_datetime}),
    }
    cursor_obj = (
        db[MATCH_COLLECTION]
        .find(mongo_filter)
        .sort(MATCH_SORT)
        .limit(page_size + 1)
    )
    docs = await cursor_obj.to_list(length=page_size + 1)
    has_more = len(docs) > page_size
    docs = docs[:page_size]

    def _cursor_for(doc):
        created = doc.get("createdAt")
        return encode_cursor({"createdAt": created.isoformat() if created else "", "_id": str(doc["_id"])})

    next_cursor = _cursor_for(docs[-1]) if has_more and docs else None
    return Page(items=[Match.from_document(d) for d in docs], next_cursor=next_cursor)


async def matched_transaction_ids_for_run(db, workspace_id: ObjectId, run_id: ObjectId) -> set:
    """Every transaction id that appears in any match of this run. Match groups
    are bounded by decisions, so loading ids is cheap; used to compute the
    unmatched remainder of a run's scope."""
    cursor = db[MATCH_COLLECTION].find(
        {"workspaceId": workspace_id, "reconciliationRunId": run_id},
        {"transactionIds": 1},
    )
    docs = await cursor.to_list(length=None)
    ids: set = set()
    for doc in docs:
        ids.update(doc.get("transactionIds") or [])
    return ids


async def insert_match(db, match: Match) -> Match:
    result = await db[MATCH_COLLECTION].insert_one(match.to_document())
    match.id = result.inserted_id
    return match


async def get_match_by_id(db, workspace_id: ObjectId, match_id: ObjectId) -> Match | None:
    """Fetch a single match by id, workspace-scoped."""
    doc = await db[MATCH_COLLECTION].find_one(
        {"_id": match_id, "workspaceId": workspace_id}
    )
    return Match.from_document(doc) if doc else None


async def approve_match(
    db, workspace_id: ObjectId, match_id: ObjectId, user_id: ObjectId, note: str = ""
) -> Match:
    """Set human_decision to APPROVED and update status to MANUAL_MATCHED."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    human_decision = {
        "action": "APPROVED",
        "userId": str(user_id),
        "at": now.isoformat(),
        "note": note,
    }
    doc = await db[MATCH_COLLECTION].find_one_and_update(
        {"_id": match_id, "workspaceId": workspace_id},
        {
            "$set": {
                "humanDecision": human_decision,
                "status": "MANUAL_MATCHED",
            }
        },
        return_document=True,
    )
    if doc is None:
        return None
    return Match.from_document(doc)


async def reject_match(
    db, workspace_id: ObjectId, match_id: ObjectId, user_id: ObjectId, note: str = ""
) -> Match:
    """Set human_decision to REJECTED."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    human_decision = {
        "action": "REJECTED",
        "userId": str(user_id),
        "at": now.isoformat(),
        "note": note,
    }
    doc = await db[MATCH_COLLECTION].find_one_and_update(
        {"_id": match_id, "workspaceId": workspace_id},
        {
            "$set": {
                "humanDecision": human_decision,
            }
        },
        return_document=True,
    )
    if doc is None:
        return None
    return Match.from_document(doc)
