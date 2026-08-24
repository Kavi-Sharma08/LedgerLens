from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from bson import ObjectId
from bson.decimal128 import Decimal128

from ..services.normalization.dates import to_utc_midnight
from .enums import Direction, TransactionStatus
from .user import utcnow


def decimal128(value) -> Decimal128:
    if isinstance(value, Decimal128):
        return value
    return Decimal128(value)


def as_decimal(value):
    """Mongo Decimal128 / None -> Python Decimal / None."""
    if value is None:
        return None
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return value


@dataclass
class Transaction:
    """Canonical (normalized) financial transaction. See
    docs/financial-data-model.md for the full field contract."""

    workspace_id: ObjectId
    source_id: ObjectId
    source_file_id: ObjectId
    raw_transaction_id: ObjectId

    transaction_date: object  # datetime.date (calendar semantics)
    amount: Decimal           # always positive; sign lives in `direction`
    currency: str
    direction: Direction

    posted_date: object | None = None          # date | None
    description: str | None = None
    normalized_description: str | None = None
    reference: str | None = None
    normalized_reference: str | None = None
    counterparty: str | None = None
    normalized_counterparty: str | None = None
    account_identifier: str | None = None
    transaction_type: str | None = None        # TransactionType value or None (unknown)
    status: str = TransactionStatus.SETTLED.value
    fingerprint: str = ""
    metadata: dict = field(default_factory=dict)
    potential_duplicate_ids: list = field(default_factory=list)
    source_record_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "sourceId": self.source_id,
            "sourceFileId": self.source_file_id,
            "rawTransactionId": self.raw_transaction_id,
            "sourceRecordId": self.source_record_id,
            "transactionDate": to_utc_midnight(self.transaction_date),
            "postedDate": to_utc_midnight(self.posted_date) if self.posted_date else None,
            "amount": decimal128(self.amount),
            "currency": self.currency,
            "direction": self.direction.value if isinstance(self.direction, Direction) else self.direction,
            "description": self.description,
            "normalizedDescription": self.normalized_description,
            "reference": self.reference,
            "normalizedReference": self.normalized_reference,
            "counterparty": self.counterparty,
            "normalizedCounterparty": self.normalized_counterparty,
            "accountIdentifier": self.account_identifier,
            "transactionType": self.transaction_type,
            "status": self.status,
            "fingerprint": self.fingerprint,
            "metadata": self.metadata,
            "potentialDuplicateIds": self.potential_duplicate_ids,
            "createdAt": self.created_at or now,
            "updatedAt": self.updated_at or now,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "Transaction":
        posted = doc.get("postedDate")
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            source_id=doc["sourceId"],
            source_file_id=doc["sourceFileId"],
            raw_transaction_id=doc["rawTransactionId"],
            source_record_id=doc.get("sourceRecordId"),
            transaction_date=doc["transactionDate"].date() if doc.get("transactionDate") else None,
            posted_date=posted.date() if posted else None,
            amount=as_decimal(doc.get("amount")),
            currency=doc.get("currency", ""),
            direction=Direction(doc.get("direction", "DEBIT")),
            description=doc.get("description"),
            normalized_description=doc.get("normalizedDescription"),
            reference=doc.get("reference"),
            normalized_reference=doc.get("normalizedReference"),
            counterparty=doc.get("counterparty"),
            normalized_counterparty=doc.get("normalizedCounterparty"),
            account_identifier=doc.get("accountIdentifier"),
            transaction_type=doc.get("transactionType"),
            status=doc.get("status", TransactionStatus.SETTLED.value),
            fingerprint=doc.get("fingerprint", ""),
            metadata=doc.get("metadata") or {},
            potential_duplicate_ids=doc.get("potentialDuplicateIds") or [],
            created_at=doc.get("createdAt"),
            updated_at=doc.get("updatedAt"),
        )
