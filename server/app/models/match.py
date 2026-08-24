from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from ..services.normalization.money import as_decimal, decimal128
from .enums import MatchType, ReconciliationStatus
from .user import utcnow


@dataclass
class Match:
    """The final reconciliation decision for a group of transactions.

    - `transaction_ids` is an array: pairwise today, ONE_TO_MANY/MANY_TO_ONE
      ready tomorrow.
    - `algorithm_decision` is immutable history; `human_decision` is layered
      on top by review flows and never replaces it."""

    workspace_id: ObjectId
    reconciliation_run_id: ObjectId
    transaction_ids: list

    match_type: MatchType = MatchType.FUZZY
    status: str = ReconciliationStatus.MATCHED.value
    confidence: object = None           # Decimal 0..1

    evidence: dict = field(default_factory=dict)
    #   {scoreBreakdown, reasons, tolerances: {dateToleranceDays, feeBand...},
    #    matchedFields: [...], mismatchedFields: [...]}
    algorithm_version: str = ""
    algorithm_decision: str = ""        # frozen copy of `status` at creation
    human_decision: dict | None = None  # {action, userId, at, note} — review phase
    created_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        return {
            "workspaceId": self.workspace_id,
            "reconciliationRunId": self.reconciliation_run_id,
            "transactionIds": self.transaction_ids,
            "matchType": self.match_type.value if isinstance(self.match_type, MatchType) else self.match_type,
            "status": self.status,
            "confidence": decimal128(self.confidence) if self.confidence is not None else None,
            "evidence": self.evidence,
            "algorithmVersion": self.algorithm_version,
            "algorithmDecision": self.algorithm_decision or self.status,
            "humanDecision": self.human_decision,
            "createdAt": self.created_at or utcnow(),
        }

    @classmethod
    def from_document(cls, doc: dict) -> "Match":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            reconciliation_run_id=doc["reconciliationRunId"],
            transaction_ids=doc.get("transactionIds") or [],
            match_type=MatchType(doc.get("matchType", MatchType.FUZZY.value)),
            status=doc.get("status", ReconciliationStatus.MATCHED.value),
            confidence=as_decimal(doc.get("confidence")),
            evidence=doc.get("evidence") or {},
            algorithm_version=doc.get("algorithmVersion", ""),
            algorithm_decision=doc.get("algorithmDecision", ""),
            human_decision=doc.get("humanDecision"),
            created_at=doc.get("createdAt"),
        )
