from datetime import date
from decimal import Decimal

from app.services.normalization.fingerprint import (
    compute_file_checksum,
    compute_fingerprint,
    compute_record_hash,
)


def _fp(**overrides):
    base = dict(
        source_id="source-1",
        currency="INR",
        amount=Decimal("5000.00"),
        direction="CREDIT",
        transaction_date=date(2026, 8, 10),
        normalized_description="payment abc",
        normalized_reference="NEFT1234",
        normalized_counterparty="abc",
        transaction_type=None,
    )
    base.update(overrides)
    return compute_fingerprint(**base)


def test_fingerprint_is_deterministic():
    assert _fp() == _fp()


def test_fingerprint_changes_with_each_content_field():
    baseline = _fp()
    assert _fp(amount=Decimal("5000.01")) != baseline
    assert _fp(transaction_date=date(2026, 8, 11)) != baseline
    assert _fp(direction="DEBIT") != baseline
    assert _fp(currency="USD") != baseline
    assert _fp(normalized_description="payment ab") != baseline
    assert _fp(normalized_reference="NEFT1235") != baseline
    assert _fp(normalized_counterparty="abcd") != baseline


def test_fingerprint_excludes_source_record_identity():
    # The same economic content arriving under a different source id is a
    # DIFFERENT fingerprint (source-scoped duplicate detection), but record
    # ids/ordinals are deliberately not part of the content hash.
    assert _fp(source_id="other-source") != _fp()


def test_fingerprint_treats_missing_as_empty_not_none_crash():
    assert _fp(normalized_description=None) == _fp(normalized_description="")


def test_record_hash_ordinal_separates_identical_lines():
    a = compute_record_hash(source_id="s", ordinal=0, canonical_raw_json='{"a":"1"}')
    b = compute_record_hash(source_id="s", ordinal=1, canonical_raw_json='{"a":"1"}')
    assert a != b
    assert a == compute_record_hash(source_id="s", ordinal=0, canonical_raw_json='{"a":"1"}')


def test_file_checksum_ignores_cosmetic_differences():
    rows_a = [{"date": "2026-08-10", "amount": "100"}, {"date": "2026-08-11", "amount": "200"}]
    rows_b = [{"amount": "100", "date": "2026-08-10"}, {"amount": "200", "date": "2026-08-11"}]
    import json

    canonical_a = json.dumps(rows_a, sort_keys=True, separators=(",", ":"))
    canonical_b = json.dumps(rows_b, sort_keys=True, separators=(",", ":"))
    assert compute_file_checksum(canonical_a) == compute_file_checksum(canonical_b)
