"""Deterministic transaction fingerprints.

A fingerprint is an *ingestion/idempotency signal*, not proof that two
transactions are economically identical:

- It is derived from stable normalized content (source, currency, amount,
  direction, date, normalized description/reference/counterparty/type).
- It deliberately EXCLUDES sourceRecordId (missing in some exports and
  unstable across others) and any file identity (the same record may arrive
  in different files).
- Identical fingerprints are surfaced as potential duplicates for review;
  they never cause silent deletion or overwrite.
"""

import hashlib
from datetime import date
from decimal import Decimal

_SEPARATOR = "\x1f"  # unit separator: cannot appear in normalized text


def compute_fingerprint(
    *,
    source_id: str,
    currency: str,
    amount: Decimal,
    direction: str,
    transaction_date: date,
    normalized_description: str | None = None,
    normalized_reference: str | None = None,
    normalized_counterparty: str | None = None,
    transaction_type: str | None = None,
) -> str:
    """Stable SHA-256 hex digest over the canonical field tuple.

    Field order matters and must never change within an algorithm version;
    a changed layout means a new fingerprint scheme (bump ALGORITHM_VERSION).
    """
    parts = [
        "v1",
        str(source_id),
        currency.upper(),
        format(amount, "f"),
        str(direction),
        transaction_date.isoformat(),
        normalized_description or "",
        normalized_reference or "",
        normalized_counterparty or "",
        transaction_type or "",
    ]
    payload = _SEPARATOR.join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_record_hash(
    *, source_id: str, ordinal: int, canonical_raw_json: str
) -> str:
    """SHA-256 over evidence identity: source + line position + raw payload.

    Used by ingestion to guarantee that replaying a file can never create a
    second copy of the same raw evidence. The ordinal keeps two legitimately
    identical lines inside one file distinct.
    """
    payload = _SEPARATOR.join([str(source_id), str(ordinal), canonical_raw_json])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_file_checksum(canonical_records_json: str) -> str:
    """Checksum over the canonical parsed record stream of a file.

    Computed from parsed content (not raw bytes) so cosmetic differences such
    as CRLF endings or trailing blank lines still recognize re-uploads as
    duplicates.
    """
    return hashlib.sha256(canonical_records_json.encode("utf-8")).hexdigest()
