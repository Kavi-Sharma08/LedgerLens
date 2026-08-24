"""Canonical Transaction model behaviour: Decimal precision survives the
MongoDB round-trip, enums stay typed, optional financial fields stay optional."""

from datetime import date, datetime, timezone
from decimal import Decimal

from bson import ObjectId
from bson.decimal128 import Decimal128

from app.models.enums import Direction, TransactionStatus
from app.models.transaction import Transaction


def _txn(**overrides):
    base = dict(
        workspace_id=ObjectId("000000000000000000000001"),
        source_id=ObjectId("00000000000000000000000a"),
        source_file_id=ObjectId("0000000000000000000000f1"),
        raw_transaction_id=ObjectId(),
        transaction_date=date(2026, 8, 10),
        amount=Decimal("5000.10"),
        currency="INR",
        direction=Direction.CREDIT,
        description="PAYMENT ABC",
        normalized_description="payment abc",
        reference="NEFT1001",
        normalized_reference="NEFT1001",
        counterparty="ABC PVT LTD",
        normalized_counterparty="abc",
    )
    base.update(overrides)
    return Transaction(**base)


def test_valid_transaction_roundtrip_preserves_exact_decimal():
    txn = _txn()
    doc = txn.to_document()
    assert isinstance(doc["amount"], Decimal128)
    restored = Transaction.from_document({**doc, "_id": ObjectId()})
    assert restored.amount == Decimal("5000.10")
    assert str(restored.amount) == "5000.10"
    assert restored.transaction_date == date(2026, 8, 10)


def test_bharat_style_paise_amounts_do_not_drift():
    for value in ("0.01", "999999999.99", "1234567.89"):
        restored = Transaction.from_document(
            {**_txn(amount=Decimal(value)).to_document(), "_id": ObjectId()}
        )
        assert restored.amount == Decimal(value)


def test_missing_optional_fields_default_cleanly():
    txn = _txn(
        description=None,
        normalized_description=None,
        reference=None,
        normalized_reference=None,
        counterparty=None,
        normalized_counterparty=None,
        posted_date=None,
        transaction_type=None,
        status=TransactionStatus.SETTLED.value,
        source_record_id=None,
    )
    doc = txn.to_document()
    restored = Transaction.from_document({**doc, "_id": ObjectId()})
    assert restored.reference is None
    assert restored.counterparty is None
    assert restored.transaction_type is None
    assert restored.source_record_id is None
    assert restored.posted_date is None
    # Status always persists as a known enum value.
    assert TransactionStatus(restored.status) == TransactionStatus.SETTLED


def test_negative_sign_is_represented_as_absolute_amount_plus_direction():
    """The canonical model stores magnitude only; the sign lives in
    `direction`. Ingestion performs this split; the model must preserve it."""
    debit = _txn(amount=Decimal("250.50"), direction=Direction.DEBIT)
    credit = _txn(amount=Decimal("250.50"), direction=Direction.CREDIT)
    assert debit.amount == credit.amount == Decimal("250.50")
    assert debit.direction != credit.direction
    restored = Transaction.from_document(
        {**debit.to_document(), "_id": ObjectId()}
    )
    assert Direction(restored.direction) == Direction.DEBIT


def test_transaction_types_and_lifecycle_statuses_roundtrip():
    for type_value, status_value in (
        ("REFUND", "SETTLED"),
        ("REVERSAL", "PENDING"),
        ("SALE", "FAILED"),
        ("FEE", "CANCELLED"),
    ):
        restored = Transaction.from_document(
            {
                **_txn(transaction_type=type_value, status=status_value).to_document(),
                "_id": ObjectId(),
            }
        )
        assert restored.transaction_type == type_value
        assert restored.status == status_value


def test_currency_is_preserved_verbatim():
    restored = Transaction.from_document(
        {**_txn(currency="USD").to_document(), "_id": ObjectId()}
    )
    assert restored.currency == "USD"


def test_duplicate_linkage_and_metadata_survive_roundtrip():
    dup_id = ObjectId()
    txn = _txn(potential_duplicate_ids=[dup_id], metadata={"extraColumns": {"branch": "X1"}})
    restored = Transaction.from_document({**txn.to_document(), "_id": ObjectId()})
    assert restored.potential_duplicate_ids == [dup_id]
    assert restored.metadata["extraColumns"]["branch"] == "X1"


def test_created_at_updated_at_defaults_to_now():
    before = datetime.now(timezone.utc).replace(microsecond=0)
    doc = _txn().to_document()
    assert doc["createdAt"] >= before
    assert doc["updatedAt"] >= doc["createdAt"]
