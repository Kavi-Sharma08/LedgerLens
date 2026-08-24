import pytest

from app.core.errors import InvalidFileError
from app.services.ingestion import extraction
from app.services.normalization.fingerprint import compute_file_checksum


CSV_ALIASES = (
    "Txn ID,Value Date,Narration,UTR,Withdrawal,Deposit,CCY,Payee\n"
    "R1,10/08/2026,payment abc,NEFT1234,,5000.00,INR,ABC LTD\n"
)


def test_resolve_fields_maps_common_bank_headers():
    resolved = extraction.resolve_fields(
        {"Txn ID": "R1", "Value Date": "10/08/2026", "Narration": "payment abc",
         "UTR": "NEFT1234", "Deposit": "5000.00", "CCY": "INR"}
    )
    assert resolved["sourceRecordId"] == "R1"
    assert resolved["date"] == "10/08/2026"
    assert resolved["description"] == "payment abc"
    assert resolved["reference"] == "NEFT1234"
    assert resolved["credit"] == "5000.00"
    assert resolved["currency"] == "INR"


def test_resolve_fields_keeps_unknown_columns_as_metadata():
    resolved = extraction.resolve_fields({"date": "2026-08-10", "branch code": "X123"})
    assert resolved["_extra"]["branch code"] == "X123"


def test_extract_csv_handles_bom_and_blank_lines():
    content = b"\xef\xbb\xbfDate,Amount,Description\n2026-08-10,100.00,abc\n\n"
    extracted = extraction.extract(content, "statement.csv", None)
    assert extracted.format_name == "csv"
    assert len(extracted.records) == 1


def test_extract_csv_rejects_unrecognized_columns():
    with pytest.raises(InvalidFileError):
        extraction.extract(b"foo,bar\n1,2\n", "weird.csv", None)


def test_extract_csv_empty_file_has_no_records():
    extracted = extraction.extract(b"Date,Amount\n", "empty.csv", "text/csv")
    assert extracted.is_empty


def test_extract_jsonl():
    content = b'{"date": "2026-08-10", "amount": "100"}\n{"date": "2026-08-11", "amount": "200"}\n'
    extracted = extraction.extract(content, "export.jsonl", None)
    assert len(extracted.records) == 2


def test_extract_jsonl_invalid_line_reports_error():
    with pytest.raises(InvalidFileError):
        extraction.extract(b'{"a": 1}\nnot json\n', "x.jsonl", None)


def test_extract_sniffs_jsonl_without_extension_hint():
    content = b'{"date": "2026-08-10"}\n'
    extracted = extraction.extract(content, "mystery", "application/octet-stream")
    assert extracted.format_name == "jsonl"


def test_file_checksum_stable_across_line_endings_and_column_order():
    rows = [extraction.resolve_fields(r) for r in extraction.extract(CSV_ALIASES.encode(), "a.csv", None).records]
    checksum_1 = compute_file_checksum(extraction.canonical_records_json(rows))

    same_lf = CSV_ALIASES.replace("\n", "\r\n").encode()
    rows2 = [extraction.resolve_fields(r) for r in extraction.extract(same_lf, "b.csv", None).records]
    checksum_2 = compute_file_checksum(extraction.canonical_records_json(rows2))

    assert checksum_1 == checksum_2
