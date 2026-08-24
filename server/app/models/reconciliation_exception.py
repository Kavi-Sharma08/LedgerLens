from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from .enums import ExceptionStatus, ExceptionReason
from .user import utcnow


@dataclass
class ReconciliationException:
    """A transaction/problem that requires investigation.

    Named ReconciliationException to avoid shadowing the Python builtin."""

    workspace_id: ObjectId
    reconciliation_run_id: ObjectId
    transaction_ids: list

    reason_code: ExceptionReason = ExceptionReason.NEEDS_REVIEW
    detail: str = ""
    status: ExceptionStatus = ExceptionStatus.OPEN
    resolution: dict | None = None      # {action, userId, at, note}
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "reconciliationRunId": self.reconciliation_run_id,
            "transactionIds": self.transaction_ids,
            "reasonCode": self.reason_code.value if isinstance(self.reason_code, ExceptionReason) else self.reason_code,
            "detail": self.detail,
            "status": self.status.value if isinstance(self.status, ExceptionStatus) else self.status,
            "resolution": self.resolution,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "ReconciliationException":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            reconciliation_run_id=doc["reconciliationRunId"],
            transaction_ids=doc.get("transactionIds") or [],
            reason_code=ExceptionReason(doc.get("reasonCode", ExceptionReason.NEEDS_REVIEW.value)),
            detail=doc.get("detail", ""),
            status=ExceptionStatus(doc.get("status", ExceptionStatus.OPEN.value)),
            resolution=doc.get("resolution"),
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
