"""Minimal in-memory MongoDB stand-in covering the operations repositories use.

Purpose: hermetic tests for workspace isolation and idempotent ingestion
without requiring a live MongoDB. It enforces declared unique indexes
(including partial filter expressions) so DuplicateKeyError semantics are
real. Not thread-safe, not a general Mongo implementation."""

import copy
import re
from datetime import datetime

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.models.enums import FileStatus


def _comparable(value):
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return value


def _match_condition(value, condition) -> bool:
    if isinstance(condition, dict):
        for op, operand in condition.items():
            if op == "$eq":
                if _comparable(value) != _comparable(operand):
                    return False
            elif op == "$ne":
                if _comparable(value) == _comparable(operand):
                    return False
            elif op == "$gt":
                if not (_comparable(value) is not None and _comparable(value) > _comparable(operand)):
                    return False
            elif op == "$gte":
                if not (_comparable(value) is not None and _comparable(value) >= _comparable(operand)):
                    return False
            elif op == "$lt":
                if not (_comparable(value) is not None and _comparable(value) < _comparable(operand)):
                    return False
            elif op == "$lte":
                if not (_comparable(value) is not None and _comparable(value) <= _comparable(operand)):
                    return False
            elif op == "$in":
                options = [_comparable(v) for v in operand]
                if _comparable(value) not in options:
                    return False
            elif op == "$nin":
                excluded = [_comparable(v) for v in operand]
                if isinstance(value, list):
                    if any(_comparable(item) in excluded for item in value):
                        return False
                elif _comparable(value) in excluded:
                    return False
            elif op == "$regex":
                if not isinstance(value, str):
                    return False
                flags = re.IGNORECASE if condition.get("$options") == "i" else 0
                if re.search(operand, value, flags) is None:
                    return False
            elif op == "$options":
                pass  # consumed by the $regex branch
            else:
                raise NotImplementedError(f"Operator {op} not supported by fake.")
        return True
    return _comparable(value) == _comparable(condition)


def _matches(doc: dict, query: dict) -> bool:
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in condition):
                return False
            continue
        if key == "$and":
            if not all(_matches(doc, sub) for sub in condition):
                return False
            continue
        value = doc.get(key)
        # MongoDB semantics: querying a field by a plain (non-operator) value
        # also matches when the field is an ARRAY containing that value.
        if isinstance(value, list) and not (isinstance(condition, dict) and all(
            op.startswith("$") for op in condition
        )):
            if not any(_comparable(item) == _comparable(condition) for item in value):
                return False
            continue
        if not _match_condition(value, condition):
            return False
    return True


def _matches_partial(doc: dict, partial: dict | None) -> bool:
    if not partial:
        return True
    return _matches(doc, partial)


# Operators MongoDB actually accepts inside partialFilterExpression.
_SUPPORTED_PARTIAL_OPERATORS = {"$eq", "$gt", "$gte", "$lt", "$lte", "$type", "$in", "$exists"}


def _validate_partial_filter(partial: dict) -> None:
    """Reject partial filter expressions real MongoDB would refuse to index."""
    for key, condition in partial.items():
        if key in ("$and", "$or"):
            for sub in condition:
                _validate_partial_filter(sub)
            continue
        if isinstance(condition, dict):
            for op in condition:
                if op not in _SUPPORTED_PARTIAL_OPERATORS:
                    raise OperationFailure(
                        f"CannotCreateIndex (67): Expression not supported in "
                        f"partial index: {op}",
                        67,
                    )


class FakeFindCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)
        self._sort_spec: list[tuple[str, int]] = []
        self._limit: int | None = None

    def sort(self, spec, direction=None):
        # Mirrors pymongo: Cursor.sort(key_or_list, direction=None) accepts
        # either a list of (field, dir) tuples or a bare field + direction.
        if direction is not None:
            spec = [(spec, direction)]
        self._sort_spec = spec
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _sorted(self) -> list[dict]:
        docs = list(self._docs)
        for field, direction in reversed(self._sort_spec):
            docs.sort(
                key=lambda d: (
                    d.get(field) is not None,
                    _comparable(d.get(field)) if d.get(field) is not None else 0,
                ),
                reverse=(direction == -1),
            )
        return docs

    async def to_list(self, length: int | None = None) -> list[dict]:
        docs = self._sorted()
        if self._limit is not None:
            docs = docs[: self._limit]
        if length is not None:
            docs = docs[:length]
        return copy.deepcopy(docs)

    # Motor cursors support `async for doc in cursor`.
    def __aiter__(self):
        self._async_iter = iter(self.to_list_sync())
        return self

    def to_list_sync(self) -> list[dict]:
        docs = self._sorted()
        if self._limit is not None:
            docs = docs[: self._limit]
        return copy.deepcopy(docs)

    async def __anext__(self):
        try:
            return next(self._async_iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, name: str, database: "FakeDatabase"):
        self.name = name
        self.database = database

    @property
    def docs(self) -> list[dict]:
        return self.database.store.setdefault(self.name, [])

    @property
    def indexes(self) -> list[dict]:
        return self.database.indexes.setdefault(self.name, [])

    def _check_unique(self, doc: dict) -> None:
        for idx in self.indexes:
            if not idx["unique"]:
                continue
            if not _matches_partial(doc, idx.get("partial")):
                continue
            key_values = []
            for field, _ in idx["keys"]:
                key_values.append(_comparable(doc.get(field)))
            for existing in self.docs:
                if not _matches_partial(existing, idx.get("partial")):
                    continue
                existing_values = [_comparable(existing.get(f)) for f, _ in idx["keys"]]
                if existing_values == key_values:
                    raise DuplicateKeyError(f"E11000 duplicate key in {self.name}: {idx['keys']}")

    async def insert_one(self, document: dict):
        doc = copy.deepcopy(document)
        if "_id" not in doc or doc["_id"] is None:
            doc["_id"] = ObjectId()
        self._check_unique(doc)
        self.docs.append(doc)
        return type("InsertResult", (), {"inserted_id": doc["_id"]})()

    async def insert_many(self, documents: list[dict]):
        inserted_ids = []
        for document in documents:
            result = await self.insert_one(document)
            inserted_ids.append(result.inserted_id)
        return type("InsertManyResult", (), {"inserted_ids": inserted_ids})()

    async def find_one(self, query: dict):
        for doc in self.docs:
            if _matches(doc, query):
                return copy.deepcopy(doc)
        return None

    def find(self, query: dict, projection: dict | None = None):
        matched = [doc for doc in self.docs if _matches(doc, query)]
        if projection:
            include = {k for k, v in projection.items() if v}
            matched = [
                {k: doc[k] for k in doc if k in include or k == "_id"}
                for doc in matched
            ]
        return FakeFindCursor(copy.deepcopy(matched))

    async def count_documents(self, query: dict) -> int:
        return sum(1 for doc in self.docs if _matches(doc, query))

    async def update_one(self, query: dict, update: dict):
        modified = 0
        for doc in self.docs:
            if _matches(doc, query):
                if "$set" in update:
                    doc.update(copy.deepcopy(update["$set"]))
                if "$addToSet" in update:
                    for field, value in update["$addToSet"].items():
                        current = doc.setdefault(field, [])
                        if value not in current:
                            current.append(copy.deepcopy(value))
                modified += 1
                break  # update_one affects at most one document
        return type("UpdateResult", (), {"modified_count": modified})()

    async def find_one_and_update(self, query: dict, update: dict, return_document=False):
        matched = None
        index = None
        for i, doc in enumerate(self.docs):
            if _matches(doc, query):
                matched = doc
                index = i
                break
        if matched is None:
            return None
        if return_document:  # ReturnDocument.AFTER -> apply then return updated
            if "$set" in update:
                matched.update(copy.deepcopy(update["$set"]))
            if "$addToSet" in update:
                for field, value in update["$addToSet"].items():
                    current = matched.setdefault(field, [])
                    if value not in current:
                        current.append(copy.deepcopy(value))
            if "$push" in update:
                for field, value in update["$push"].items():
                    matched.setdefault(field, []).append(copy.deepcopy(value))
            self.database.store[self.name][index] = matched
            return copy.deepcopy(matched)
        return copy.deepcopy(matched)  # ReturnDocument.BEFORE

    async def delete_many(self, query: dict):
        before = len(self.docs)
        self.database.store[self.name] = [d for d in self.docs if not _matches(d, query)]
        return type("DeleteResult", (), {"deleted_count": before - len(self.database.store[self.name])})()


class FakeDatabase:
    """Async-compatible stand-in for Motor's database object."""

    def __init__(self):
        self.store: dict[str, list[dict]] = {}
        self.indexes: dict[str, list[dict]] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return FakeCollection(name, self)

    def declare_index(self, collection: str, keys: list[tuple[str, int]], unique: bool = False,
                      partial: dict | None = None) -> None:
        # Faithfulness guard: real MongoDB only supports a small operator set
        # inside partialFilterExpression ($eq, $exists:true, $gt/$gte/$lt/$lte,
        # $type, top-level $and). Rejecting unsupported operators here mirrors
        # the server's CannotCreateIndex (code 67) so an index declaration that
        # would fail on a live database fails in tests too.
        if partial:
            _validate_partial_filter(partial)
        self.indexes.setdefault(collection, []).append(
            {"keys": list(keys), "unique": unique, "partial": partial}
        )

    def declare_standard_indexes(self) -> None:
        """The Phase-2 unique constraints repositories rely on."""
        self.declare_index("sources", [("workspaceId", 1), ("name", 1)], unique=True)
        self.declare_index(
            "source_files",
            [("workspaceId", 1), ("sourceId", 1), ("checksum", 1)],
            unique=True,
            # Mirrors app.core.database.INDEXES: $ne is not a legal
            # partialFilterExpression operator on real MongoDB.
            partial={
                "status": {
                    "$in": [s.value for s in FileStatus if s is not FileStatus.DUPLICATE]
                }
            },
        )
        self.declare_index(
            "raw_transactions",
            [("workspaceId", 1), ("sourceId", 1), ("recordHash", 1)],
            unique=True,
        )
