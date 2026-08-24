import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from bson import ObjectId

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.models.enums import Direction  # noqa: E402
from app.models.transaction import Transaction  # noqa: E402
from app.services.normalization.text import (  # noqa: E402
    normalize_counterparty,
    normalize_reference,
    normalize_text,
)

WORKSPACE_ID = ObjectId("000000000000000000000001")
SOURCE_A = ObjectId("00000000000000000000000a")
SOURCE_B = ObjectId("00000000000000000000000b")
FILE_A = ObjectId("0000000000000000000000f1")


class InMemoryStorage:
    """Hermetic stand-in for the local-disk upload backend."""

    def __init__(self):
        self.files = {}

    def save(self, workspace_id, original_file_name, content):
        key = f"{workspace_id}/{uuid.uuid4().hex}"
        self.files[key] = bytes(content)
        return key, len(content)

    def open(self, storage_key):
        return self.files[storage_key]


@pytest.fixture(autouse=True)
def hermetic_storage():
    from app.services.ingestion import storage

    backend = InMemoryStorage()
    storage.set_storage(backend)
    yield backend
    storage.set_storage(None)


@pytest.fixture()
def fake_db():
    from tests.fakes.fake_mongo import FakeDatabase

    db = FakeDatabase()
    db.declare_standard_indexes()
    return db


_counter = {"n": 0}


def make_txn(
    *,
    rid: str = "T1",
    txn_date: tuple = (2026, 8, 10),
    amount: str = "100.00",
    currency: str = "INR",
    direction: str = "CREDIT",
    description: str | None = None,
    reference: str | None = None,
    counterparty: str | None = None,
    txn_type: str | None = None,
    status: str = "SETTLED",
    source_id=None,
    source_record_id: str | None = None,
) -> Transaction:
    _counter["n"] += 1
    return Transaction(
        workspace_id=WORKSPACE_ID,
        source_id=source_id or SOURCE_A,
        source_file_id=FILE_A,
        raw_transaction_id=ObjectId(),
        transaction_date=date(*txn_date),
        amount=Decimal(amount),
        currency=currency,
        direction=Direction(direction),
        description=description,
        normalized_description=normalize_text(description),
        reference=reference,
        normalized_reference=normalize_reference(reference),
        counterparty=counterparty,
        normalized_counterparty=normalize_counterparty(counterparty),
        transaction_type=txn_type,
        status=status,
        source_record_id=source_record_id,
        fingerprint=f"fp-{rid}-{_counter['n']}",
        id=ObjectId(),
    )


def spec_to_txn(spec, workspace_id, source_id):
    """Convert a synthetic RecordSpec into a canonical Transaction."""
    from app.synthetic.dataset import RecordSpec

    assert isinstance(spec, RecordSpec)
    y, m, d = (int(part) for part in spec.date.split("-"))
    signed = Decimal(spec.amount)
    return make_txn(
        rid=spec.rid or f"spec-{_counter['n']}",
        txn_date=(y, m, d),
        amount=str(abs(signed)),
        currency=spec.currency,
        direction="DEBIT" if signed < 0 else "CREDIT",
        description=spec.description or None,
        reference=spec.reference or None,
        counterparty=spec.counterparty or None,
        txn_type=spec.type or None,
        status=spec.status if spec.status in {"PENDING", "SETTLED", "FAILED", "CANCELLED"} else "SETTLED",
        source_id=source_id,
        source_record_id=spec.rid or None,
    )
