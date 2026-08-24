from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from ..services.normalization.money import as_decimal, decimal128
from .enums import CandidateStatus
from .user import utcnow


@dataclass
class MatchCandidate:
    """A scored pair of transactions considered during a run.

    Candidates are evidence, not decisions: even rejected candidates are kept
    so the future AI agent (and humans) can see what the algorithm saw."""

    workspace_id: ObjectId
    reconciliation_run_id: ObjectId

    transaction_a_id: ObjectId
    transaction_b_id: ObjectId

    score: object                       # Decimal 0..1
    score_breakdown: dict = field(default_factory=dict)  # {amountScore: ..., ...}
    reasons: list = field(default_factory=list)
    status: CandidateStatus = CandidateStatus.CONSIDERED
    created_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        return {
            "workspaceId": self.workspace_id,
            "reconciliationRunId": self.reconciliation_run_id,
            "transactionAId": self.transaction_a_id,
            "transactionBId": self.transaction_b_id,
            "score": decimal128(self.score),
            "scoreBreakdown": self.score_breakdown,
            "reasons": self.reasons,
            "status": self.status.value if isinstance(self.status, CandidateStatus) else self.status,
            "createdAt": self.created_at or utcnow(),
        }

    @classmethod
    def from_document(cls, doc: dict) -> "MatchCandidate":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            reconciliation_run_id=doc["reconciliationRunId"],
            transaction_a_id=doc["transactionAId"],
            transaction_b_id=doc["transactionBId"],
            score=as_decimal(doc.get("score")),
            score_breakdown=doc.get("scoreBreakdown") or {},
            reasons=doc.get("reasons") or [],
            status=CandidateStatus(doc.get("status", CandidateStatus.CONSIDERED.value)),
            created_at=doc.get("createdAt"),
        )
