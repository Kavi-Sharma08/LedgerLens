from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..models.transaction import Transaction
from ..services.normalization.dates import to_utc_midnight
from .common import (
    Page,
    build_filter_from_cursor,
    clamp_page_size,
    decode_cursor,
    encode_cursor,
    iso_to_datetime,
)

COLLECTION = "transactions"

LIST_SORT = [("transactionDate", -1), ("_id", -1)]


class TransactionFilter:
    """Extensible query description. New filters are added here and translated
    in `build_query` — repositories never grow ad-hoc parameter lists."""

    def __init__(
        self,
        *,
        source_id: ObjectId | None = None,
        source_file_id: ObjectId | None = None,
        date_from=None,
        date_to=None,
        currency: str | None = None,
        direction: str | None = None,
        status: str | None = None,
        transaction_type: str | None = None,
        search: str | None = None,
        exclude_ids: list[ObjectId] | None = None,
    ):
        self.source_id = source_id
        self.source_file_id = source_file_id
        self.date_from = date_from
        self.date_to = date_to
        self.currency = currency
        self.direction = direction
        self.status = status
        self.transaction_type = transaction_type
        self.search = search
        self.exclude_ids = exclude_ids

    def build_query(self, workspace_id: ObjectId) -> dict:
        """Workspace isolation is unconditional — it is not a filter the
        caller can omit."""
        query: dict = {"workspaceId": workspace_id}
        if self.source_id is not None:
            query["sourceId"] = self.source_id
        if self.source_file_id is not None:
            query["sourceFileId"] = self.source_file_id
        if self.date_from is not None or self.date_to is not None:
            range_query: dict = {}
            if self.date_from is not None:
                range_query["$gte"] = to_utc_midnight(self.date_from)
            if self.date_to is not None:
                range_query["$lte"] = to_utc_midnight(self.date_to)
            query["transactionDate"] = range_query
        if self.currency is not None:
            query["currency"] = self.currency.upper()
        if self.direction is not None:
            query["direction"] = self.direction.upper()
        if self.status is not None:
            query["status"] = self.status.upper()
        if self.transaction_type is not None:
            query["transactionType"] = self.transaction_type.upper()
        if self.search:
            import re

            pattern = {"$regex": re.escape(self.search.strip()), "$options": "i"}
            query["$or"] = [
                {"reference": pattern},
                {"description": pattern},
                {"counterparty": pattern},
            ]
        if self.exclude_ids:
            query["_id"] = {"$nin": list(self.exclude_ids)}
        return query


async def insert_transaction(db, workspace_id: ObjectId, txn: Transaction) -> Transaction:
    try:
        result = await db[COLLECTION].insert_one(txn.to_document())
    except DuplicateKeyError:
        # Canonical rows have no unique index today; this guards future ones.
        raise
    txn.id = result.inserted_id
    return txn


async def get_by_id(db, workspace_id: ObjectId, txn_id: str | ObjectId) -> Transaction | None:
    try:
        _id = ObjectId(str(txn_id))
    except Exception:
        return None
    doc = await db[COLLECTION].find_one({"_id": _id, "workspaceId": workspace_id})
    return Transaction.from_document(doc) if doc else None


async def find_fingerprint_matches(
    db, workspace_id: ObjectId, source_id: ObjectId, fingerprint: str
) -> list[Transaction]:
    cursor = db[COLLECTION].find(
        {
            "workspaceId": workspace_id,
            "sourceId": source_id,
            "fingerprint": fingerprint,
        }
    )
    docs = await cursor.to_list(length=None)
    return [Transaction.from_document(d) for d in docs]


async def link_potential_duplicate(db, workspace_id: ObjectId, txn_id: ObjectId, duplicate_id: ObjectId) -> None:
    for a, b in ((txn_id, duplicate_id), (duplicate_id, txn_id)):
        await db[COLLECTION].update_one(
            {"_id": a, "workspaceId": workspace_id},
            {"$addToSet": {"potentialDuplicateIds": b}, "$set": {"updatedAt": datetime.now(timezone.utc)}},
        )


async def list_transactions(
    db,
    workspace_id: ObjectId,
    query_filter: TransactionFilter,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    page_size = clamp_page_size(limit)
    query = query_filter.build_query(workspace_id)
    mongo_filter = {
        **query,
        **build_filter_from_cursor(
            decode_cursor(cursor), LIST_SORT, cast={"transactionDate": iso_to_datetime}
        ),
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
                "transactionDate": docs[-1]["transactionDate"].isoformat(),
                "_id": str(docs[-1]["_id"]),
            }
        )
        if has_more and docs
        else None
    )
    return Page(items=[Transaction.from_document(d) for d in docs], next_cursor=next_cursor)


async def list_transactions_for_sources(
    db,
    workspace_id: ObjectId,
    source_ids: list[ObjectId],
    query_filter: TransactionFilter | None = None,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> Page:
    """Cursor-paginated transactions restricted to the given sources (a run's
    scope). Used by the unmatched read model."""
    query_filter = query_filter or TransactionFilter()
    query = query_filter.build_query(workspace_id)
    existing = query.pop("sourceId", None)
    scope: dict = {"$in": list(source_ids)}
    if existing is not None:
        # A filter already pinned one source; intersect it with the scope.
        if isinstance(existing, dict):
            existing["$in"] = list(source_ids)
            scope = existing
        elif existing in source_ids:
            scope = {"$in": [existing]}
        else:
            return Page(items=[], next_cursor=None)
    query["sourceId"] = scope

    page_size = clamp_page_size(limit)
    mongo_filter = {
        **query,
        **build_filter_from_cursor(
            decode_cursor(cursor), LIST_SORT, cast={"transactionDate": iso_to_datetime}
        ),
    }
    cursor_obj = db[COLLECTION].find(mongo_filter).sort(LIST_SORT).limit(page_size + 1)
    docs = await cursor_obj.to_list(length=page_size + 1)
    has_more = len(docs) > page_size
    docs = docs[:page_size]
    next_cursor = (
        encode_cursor(
            {
                "transactionDate": docs[-1]["transactionDate"].isoformat(),
                "_id": str(docs[-1]["_id"]),
            }
        )
        if has_more and docs
        else None
    )
    return Page(items=[Transaction.from_document(d) for d in docs], next_cursor=next_cursor)


async def count_transactions(db, workspace_id: ObjectId, query_filter: TransactionFilter) -> int:
    return await db[COLLECTION].count_documents(query_filter.build_query(workspace_id))


async def list_for_sources(
    db,
    workspace_id: ObjectId,
    source_ids: list[ObjectId],
    *,
    date_from=None,
    date_to=None,
) -> list[Transaction]:
    """Load the full scope of a reconciliation run. Runs operate on bounded
    datasets; streaming/batching arrives with the incremental engine."""
    query_filter = TransactionFilter(
        source_id=source_ids[0] if len(source_ids) == 1 else None,
        date_from=date_from,
        date_to=date_to,
    )
    query = query_filter.build_query(workspace_id)
    if len(source_ids) != 1:
        query["sourceId"] = {"$in": [sid for sid in source_ids]}
    cursor = (
        db[COLLECTION]
        .find(query)
        .sort([("transactionDate", 1), ("_id", 1)])
    )
    docs = await cursor.to_list(length=None)
    return [Transaction.from_document(d) for d in docs]
