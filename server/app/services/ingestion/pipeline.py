"""Normalization + persistence pipeline.

Stages (kept as separate functions per the phase plan — never one giant
function):

    raw file -> extraction -> raw records -> normalization -> validation
             -> fingerprint/idempotency -> persistence

Idempotency layers enforced here:
1. file checksum (checked by the service before this pipeline runs)
2. raw recordHash unique index (evidence level, inside `ingest_extracted`)
3. transaction fingerprint (duplicate *detection*, never silent deletion)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId

from ...models.enums import Direction, FileStatus, TransactionStatus
from ...models.raw_transaction import RawTransaction
from ...models.source import Source
from ...models.source_file import SourceFile
from ...models.transaction import Transaction
from ...repositories import (
    raw_transaction_repository,
    source_file_repository,
    transaction_repository,
)
from ..normalization import (
    DateError,
    MoneyError,
    compute_fingerprint,
    compute_record_hash,
    normalize_counterparty,
    normalize_reference,
    normalize_text,
    parse_amount,
    parse_date_value,
    quantize_for_currency,
    validate_currency,
)
from . import extraction
from .extraction import ExtractedFile, resolve_fields

logger = logging.getLogger("ledgerlens.ingestion")


@dataclass
class RowError:
    ordinal: int
    message: str


@dataclass
class IngestionSummary:
    file: SourceFile | None = None
    processed_count: int = 0
    skipped_duplicate_count: int = 0
    errors: list = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def is_duplicate(self) -> bool:
        return self.file is not None and self.file.duplicate_of_id is not None


@dataclass
class NormalizedFields:
    """Canonical result of normalizing one row."""

    transaction_date: object
    posted_date: object | None
    amount: Decimal
    currency: str
    direction: Direction
    description: str | None
    normalized_description: str | None
    reference: str | None
    normalized_reference: str | None
    counterparty: str | None
    normalized_counterparty: str | None
    transaction_type: str | None
    status: str
    fingerprint: str
    source_record_id: str | None
    metadata: dict = field(default_factory=dict)


def amount_and_direction(resolved: dict) -> tuple[Decimal, Direction]:
    """Interpret signed amount / debit-credit columns into an absolute amount
    plus direction. Explicit debit/credit columns always win over a signed
    amount because sign conventions differ per system (phase spec #26)."""
    debit_text = (resolved.get("debit") or "").strip()
    credit_text = (resolved.get("credit") or "").strip()

    if debit_text or credit_text:
        try:
            debit = abs(parse_amount(debit_text)) if debit_text else Decimal("0")
            credit = abs(parse_amount(credit_text)) if credit_text else Decimal("0")
        except MoneyError as exc:
            raise ValueError(f"Invalid debit/credit value: {exc}") from exc
        if debit > 0 and credit > 0:
            raise ValueError("Row has both debit and credit values; cannot determine direction.")
        if debit > 0:
            return debit, Direction.DEBIT
        if credit > 0:
            return credit, Direction.CREDIT
        raise ValueError("Debit/credit values are zero.")

    amount_text = (resolved.get("amount") or "").strip()
    if not amount_text:
        raise ValueError("Row has no amount, debit or credit value.")
    try:
        signed = parse_amount(amount_text)
    except MoneyError as exc:
        raise ValueError(str(exc)) from exc
    direction = Direction.DEBIT if signed < 0 else Direction.CREDIT
    return abs(signed), direction


def normalize_row(resolved: dict, source: Source) -> NormalizedFields:
    """Pure normalization of one resolved row. Raises ValueError with a
    human-safe message when validation fails."""
    if not (resolved.get("date") or "").strip():
        raise ValueError("Row has no transaction date.")
    try:
        transaction_date = parse_date_value(resolved["date"])
    except DateError as exc:
        raise ValueError(str(exc)) from exc

    raw_amount, direction = amount_and_direction(resolved)

    currency_text = (resolved.get("currency") or "").strip() or source.currency
    try:
        currency = validate_currency(currency_text)
    except MoneyError as exc:
        raise ValueError(str(exc)) from exc

    amount = quantize_for_currency(raw_amount, currency)

    description = (resolved.get("description") or "").strip() or None
    reference = (resolved.get("reference") or "").strip() or None
    counterparty = (resolved.get("counterparty") or "").strip() or None

    posted_raw = (resolved.get("postedDate") or "").strip()
    posted_date = None
    if posted_raw:
        try:
            posted_date = parse_date_value(posted_raw)
        except DateError as exc:
            raise ValueError(str(exc)) from exc

    transaction_type = (resolved.get("type") or "").strip().upper() or None
    valid_types = {t.value for t in TransactionStatus} | {
        "SALE", "PAYMENT", "REFUND", "REVERSAL", "FEE", "TRANSFER", "ADJUSTMENT",
    }
    if transaction_type is not None and transaction_type not in valid_types:
        logger.info("unknown transaction type passthrough: %s", transaction_type)

    status_text = (resolved.get("status") or "").strip().upper() or TransactionStatus.SETTLED.value
    if status_text not in {s.value for s in TransactionStatus}:
        status_text = TransactionStatus.SETTLED.value

    normalized_description = normalize_text(description)
    normalized_reference = normalize_reference(reference)
    normalized_counterparty = normalize_counterparty(counterparty)

    fingerprint = compute_fingerprint(
        source_id=str(source.id),
        currency=currency,
        amount=amount,
        direction=direction.value,
        transaction_date=transaction_date,
        normalized_description=normalized_description,
        normalized_reference=normalized_reference,
        normalized_counterparty=normalized_counterparty,
        transaction_type=transaction_type,
    )

    extras = resolved.get("_extra") or {}

    return NormalizedFields(
        transaction_date=transaction_date,
        posted_date=posted_date,
        amount=amount,
        currency=currency,
        direction=direction,
        description=description,
        normalized_description=normalized_description,
        reference=reference,
        normalized_reference=normalized_reference,
        counterparty=counterparty,
        normalized_counterparty=normalized_counterparty,
        transaction_type=transaction_type,
        status=status_text,
        fingerprint=fingerprint,
        source_record_id=(resolved.get("sourceRecordId") or "").strip() or None,
        metadata={"extraColumns": extras} if extras else {},
    )


async def ingest_extracted(
    db,
    workspace_id: ObjectId,
    source: Source,
    source_file: SourceFile,
    extracted: ExtractedFile,
) -> IngestionSummary:
    """Persist an already-extracted file through the full pipeline."""
    summary = IngestionSummary(file=source_file)

    await source_file_repository.update_processing_result(
        db, workspace_id, source_file.id,
        status=FileStatus.PROCESSING,
        transaction_count=0, skipped_duplicate_count=0, error_count=0,
    )
    source_file.status = FileStatus.PROCESSING

    canonical_rows = [resolve_fields(row) for row in extracted.records]
    record_hashes = [
        compute_record_hash(
            source_id=str(source.id),
            ordinal=ordinal,
            canonical_raw_json=extraction.canonical_records_json([row]),
        )
        for ordinal, row in enumerate(canonical_rows)
    ]

    for ordinal, (original_row, resolved_row) in enumerate(zip(extracted.records, canonical_rows)):
        try:
            fields = normalize_row(resolved_row, source)
        except ValueError as exc:
            summary.errors.append(RowError(ordinal=ordinal, message=str(exc)))
            logger.info(
                "row rejected workspace=%s source=%s file=%s ordinal=%s reason=%s",
                workspace_id, source.id, source_file.id, ordinal, exc,
            )
            continue

        raw = RawTransaction(
            workspace_id=workspace_id,
            source_id=source.id,
            source_file_id=source_file.id,
            ordinal=ordinal,
            raw_data=dict(original_row),
            record_hash=record_hashes[ordinal],
            source_record_id=fields.source_record_id,
            imported_at=datetime.now(timezone.utc),
        )
        raw, inserted = await raw_transaction_repository.insert_raw(db, workspace_id, raw)
        if not inserted:
            summary.skipped_duplicate_count += 1
            logger.info(
                "duplicate evidence skipped workspace=%s source=%s file=%s ordinal=%s",
                workspace_id, source.id, source_file.id, ordinal,
            )
            continue

        txn = Transaction(
            workspace_id=workspace_id,
            source_id=source.id,
            source_file_id=source_file.id,
            raw_transaction_id=raw.id,
            source_record_id=fields.source_record_id,
            transaction_date=fields.transaction_date,
            posted_date=fields.posted_date,
            amount=fields.amount,
            currency=fields.currency,
            direction=fields.direction,
            description=fields.description,
            normalized_description=fields.normalized_description,
            reference=fields.reference,
            normalized_reference=fields.normalized_reference,
            counterparty=fields.counterparty,
            normalized_counterparty=fields.normalized_counterparty,
            account_identifier=source.account_identifier,
            transaction_type=fields.transaction_type,
            status=fields.status,
            fingerprint=fields.fingerprint,
            metadata=fields.metadata,
        )
        await transaction_repository.insert_transaction(db, workspace_id, txn)
        summary.processed_count += 1

        # Duplicate detection: identical content fingerprint within this
        # source is surfaced for review, never silently deleted.
        existing = await transaction_repository.find_fingerprint_matches(
            db, workspace_id, source.id, fields.fingerprint
        )
        others = [t for t in existing if t.id != txn.id]
        for other in others[:5]:  # fingerprints are high-cardinality; bounded
            await transaction_repository.link_potential_duplicate(
                db, workspace_id, txn.id, other.id
            )

    await _finalize_file_status(db, workspace_id, source_file, summary)
    return summary


async def _finalize_file_status(
    db, workspace_id: ObjectId, source_file: SourceFile, summary: IngestionSummary
) -> None:
    if summary.error_count == 0:
        final_status = FileStatus.PROCESSED
        error_message = None
    elif summary.processed_count > 0:
        final_status = FileStatus.PARTIAL
        first = summary.errors[0].message if summary.errors else None
        error_message = f"{summary.error_count} record(s) could not be imported." + (
            f" First issue: {first}" if first else ""
        )
    else:
        final_status = FileStatus.FAILED
        error_message = (
            summary.errors[0].message if summary.errors else "No records could be parsed."
        )

    await source_file_repository.update_processing_result(
        db,
        workspace_id,
        source_file.id,
        status=final_status,
        transaction_count=summary.processed_count,
        skipped_duplicate_count=summary.skipped_duplicate_count,
        error_count=summary.error_count,
        error=error_message,
    )
    # Keep the in-memory object consistent with what was persisted: the
    # summary's file is what API responses serialize.
    source_file.status = final_status
    source_file.transaction_count = summary.processed_count
    source_file.skipped_duplicate_count = summary.skipped_duplicate_count
    source_file.error_count = summary.error_count
    source_file.error = error_message
