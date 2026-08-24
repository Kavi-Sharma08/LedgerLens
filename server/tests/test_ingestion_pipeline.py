import pytest

from app.models.enums import FileStatus, SourceType
from app.models.source_file import SourceFile
from app.repositories import (
    raw_transaction_repository,
    source_file_repository,
    transaction_repository,
)
from app.services.ingestion import extraction, pipeline
from app.services.source_service import create_source, upload_source_file

from .conftest import WORKSPACE_ID


def csv_bytes(rows: str) -> bytes:
    header = "TxnId,Date,Amount,Currency,Description,Reference,Counterparty,Type,Status\n"
    return (header + rows).encode("utf-8")


GOOD_ROWS = (
    "T1,2026-08-10,1500.00,INR,PAYMENT ABC PVT LTD,NEFT1001,ABC PVT LTD,SALE,\n"
    "T2,2026-08-10,-250.50,,UTILITY BILL XYZ,,,\n"
    'T3,11/08/2026,"4,200.75",INR,NEFT CREDIT QRS,UTR77,QRS LIMITED,\n'
)


async def _make_source(fake_db, name="Bank"):
    return await create_source(
        fake_db, WORKSPACE_ID, name=name, source_type=SourceType.BANK, currency="INR"
    )


@pytest.mark.asyncio
async def test_happy_path_ingests_rows_and_normalizes(fake_db):
    source = await _make_source(fake_db)
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="statement.csv", mime_type="text/csv",
        content=csv_bytes(GOOD_ROWS), uploaded_by=None,
    )
    assert summary.processed_count == 3
    assert summary.error_count == 0
    assert not summary.is_duplicate
    assert summary.file.status == FileStatus.PROCESSED

    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    assert len(txns) == 3

    by_rid = {t.source_record_id: t for t in txns}
    # Signed amount became absolute + DEBIT direction.
    assert by_rid["T2"].direction.value == "DEBIT"
    assert str(by_rid["T2"].amount) == "250.50"
    # Thousands separators and day-first dates are handled.
    assert by_rid["T3"].transaction_date.isoformat() == "2026-08-11"
    assert str(by_rid["T3"].amount) == "4200.75"
    # Missing currency falls back to the source default.
    assert by_rid["T2"].currency == "INR"

    raws = (await raw_transaction_repository.list_for_file(
        fake_db, WORKSPACE_ID, by_rid["T1"].source_file_id
    )).items
    assert len(raws) == 3
    # Original evidence is preserved verbatim.
    assert raws[0].raw_data["Date"] == "2026-08-10"


@pytest.mark.asyncio
async def test_reuploading_identical_content_is_a_duplicate(fake_db):
    source = await _make_source(fake_db)
    content = csv_bytes(GOOD_ROWS)

    first = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="a.csv", mime_type="text/csv", content=content, uploaded_by=None,
    )
    second = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="b.csv", mime_type="text/csv", content=content, uploaded_by=None,
    )

    assert first.processed_count == 3
    assert second.is_duplicate
    assert second.file.duplicate_of_id == first.file.id
    assert second.processed_count == 0
    assert second.file.status == FileStatus.DUPLICATE

    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    assert len(txns) == 3  # nothing re-ingested


@pytest.mark.asyncio
async def test_record_hash_makes_evidence_replay_idempotent(fake_db):
    source = await _make_source(fake_db)
    extracted = extraction.extract(csv_bytes(GOOD_ROWS), "a.csv", None)

    async def _new_file(name, checksum):
        return await source_file_repository.create_file(
            fake_db, WORKSPACE_ID,
            SourceFile(
                workspace_id=WORKSPACE_ID, source_id=source.id,
                file_name=name, original_file_name=name,
                checksum=checksum, mime_type="text/csv", file_size=1,
            ),
        )

    summary_1 = await pipeline.ingest_extracted(
        fake_db, WORKSPACE_ID, source, await _new_file("one.csv", "c1"), extracted
    )
    assert summary_1.processed_count == 3

    summary_2 = await pipeline.ingest_extracted(
        fake_db, WORKSPACE_ID, source, await _new_file("two.csv", "c2"), extracted
    )
    assert summary_2.skipped_duplicate_count == 3
    assert summary_2.processed_count == 0

    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    assert len(txns) == 3


@pytest.mark.asyncio
async def test_legitimately_identical_lines_are_kept_and_flagged(fake_db):
    source = await _make_source(fake_db)
    row = "D1,2026-08-10,500.00,INR,PAYMENT DUP CO,REF1,DUP CO,SALE,\n"
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="dups.csv", mime_type="text/csv",
        content=csv_bytes(row + row), uploaded_by=None,
    )
    assert summary.processed_count == 2  # ordinal differs -> distinct evidence

    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    assert len(txns) == 2
    first, second = txns[0], txns[1]
    # Duplicate detection links both ways but never deletes anything.
    assert first.id in (second.potential_duplicate_ids or [])
    assert second.id in (first.potential_duplicate_ids or [])


@pytest.mark.asyncio
async def test_bad_rows_become_partial_not_fatal(fake_db):
    source = await _make_source(fake_db)
    rows = (
        "OK1,2026-08-10,100.00,INR,fine,REF,CP,\n"
        "BAD1,not-a-date,100.00,INR,bad date,,\n"
        "BAD2,2026-08-11,abc,INR,bad amount,,\n"
        "OK2,2026-08-12,200.00,INR,fine too,REF2,CP2\n"
    )
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="mixed.csv", mime_type="text/csv", content=csv_bytes(rows), uploaded_by=None,
    )
    assert summary.processed_count == 2
    assert summary.error_count == 2
    assert summary.file.status == FileStatus.PARTIAL
    assert all(e.message for e in summary.errors)
    assert [e.ordinal for e in summary.errors] == [1, 2]

    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    assert sorted(t.source_record_id for t in txns) == ["OK1", "OK2"]


@pytest.mark.asyncio
async def test_all_bad_rows_fail_the_file(fake_db):
    source = await _make_source(fake_db)
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="bad.csv", mime_type="text/csv",
        content=csv_bytes("B1,nope,10.00,INR,x,,\n"), uploaded_by=None,
    )
    assert summary.processed_count == 0
    assert summary.file.status == FileStatus.FAILED


@pytest.mark.asyncio
async def test_debit_credit_columns_drive_direction(fake_db):
    source = await _make_source(fake_db)
    content = (
        b"Date,Withdrawal,Deposit,Description\n"
        b"2026-08-10,,900.00,credit row\n"
        b"2026-08-11,120.00,,debit row\n"
    )
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="dc.csv", mime_type="text/csv", content=content, uploaded_by=None,
    )
    assert summary.error_count == 0
    txns = await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id])
    directions = {t.description: t.direction.value for t in txns}
    assert directions == {"credit row": "CREDIT", "debit row": "DEBIT"}

    ambiguous = (
        b"Date,Withdrawal,Deposit,Description\n"
        b"2026-08-10,5.00,5.00,ambiguous\n"
    )
    summary_2 = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="both.csv", mime_type="text/csv", content=ambiguous, uploaded_by=None,
    )
    assert summary_2.error_count == 1


@pytest.mark.asyncio
async def test_invalid_currency_in_row_is_rejected(fake_db):
    source = await _make_source(fake_db)
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="ccy.csv", mime_type="text/csv",
        content=csv_bytes("T1,2026-08-10,100.00,ZZZ,bad ccy,,\n"), uploaded_by=None,
    )
    assert summary.error_count == 1
    assert "currency" in summary.errors[0].message.lower()


@pytest.mark.asyncio
async def test_rows_without_txn_id_still_ingest(fake_db):
    source = await _make_source(fake_db)
    content = b"Date,Amount,Description\n2026-08-10,300.00,no id here\n"
    summary = await upload_source_file(
        fake_db, WORKSPACE_ID, source=source,
        file_name="noid.csv", mime_type="text/csv", content=content, uploaded_by=None,
    )
    assert summary.processed_count == 1
    txn = (await transaction_repository.list_for_sources(fake_db, WORKSPACE_ID, [source.id]))[0]
    assert txn.source_record_id is None
