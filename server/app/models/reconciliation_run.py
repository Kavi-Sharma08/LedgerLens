from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from ..services.normalization.dates import to_utc_midnight
from .enums import RunStatus
from .user import utcnow


@dataclass
class ReconciliationRun:
    """One reconciliation operation over a defined set of sources/transactions.

    `algorithm_version` + the frozen `config` snapshot make every historical
    run reproducible and explainable."""

    workspace_id: ObjectId
    source_ids: list

    status: RunStatus = RunStatus.QUEUED
    transaction_scope: dict = field(default_factory=dict)  # {dateFrom?, dateTo?}
    started_at: datetime | None = None
    completed_at: datetime | None = None

    total_transactions: int = 0
    matched_count: int = 0
    likely_match_count: int = 0
    ambiguous_count: int = 0
    unmatched_count: int = 0
    exception_count: int = 0

    algorithm_version: str = ""
    config: dict = field(default_factory=dict)
    error: str | None = None
    metadata: dict = field(default_factory=dict)
    id: ObjectId | None = None

    def to_document(self) -> dict:
        return {
            "workspaceId": self.workspace_id,
            "sourceIds": self.source_ids,
            "status": self.status.value if isinstance(self.status, RunStatus) else self.status,
            "transactionScope": self.transaction_scope,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "totalTransactions": self.total_transactions,
            "matchedCount": self.matched_count,
            "likelyMatchCount": self.likely_match_count,
            "ambiguousCount": self.ambiguous_count,
            "unmatchedCount": self.unmatched_count,
            "exceptionCount": self.exception_count,
            "algorithmVersion": self.algorithm_version,
            "config": self.config,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "ReconciliationRun":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            source_ids=doc.get("sourceIds") or [],
            status=RunStatus(doc.get("status", RunStatus.QUEUED.value)),
            transaction_scope=doc.get("transactionScope") or {},
            started_at=doc.get("startedAt"),
            completed_at=doc.get("completedAt"),
            total_transactions=doc.get("totalTransactions", 0),
            matched_count=doc.get("matchedCount", 0),
            likely_match_count=doc.get("likelyMatchCount", 0),
            ambiguous_count=doc.get("ambiguousCount", 0),
            unmatched_count=doc.get("unmatchedCount", 0),
            exception_count=doc.get("exceptionCount", 0),
            algorithm_version=doc.get("algorithmVersion", ""),
            config=doc.get("config") or {},
            error=doc.get("error"),
            metadata=doc.get("metadata") or {},
        )
