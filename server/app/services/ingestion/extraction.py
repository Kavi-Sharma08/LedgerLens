"""Extraction layer: raw file bytes -> ordered record rows.

Parsers return the ORIGINAL row dictionaries (evidence) plus a resolved view
using canonical field names. The canonical resolution is also what file
checksums are computed over, so re-uploads of the same logical content are
recognized regardless of cosmetic formatting.

Supported formats today: CSV (with header alias mapping) and JSON Lines.
PDF/OCR is deliberately out of scope for this phase."""

import csv
import io
import json
import re
from dataclasses import dataclass, field

from ...core.errors import InvalidFileError

# Canonical field -> accepted header aliases (normalized: lowercase, spaces).
FIELD_ALIASES: dict[str, set[str]] = {
    "sourceRecordId": {"transactionid", "txn id", "txn id", "txnid", "transaction id", "id", "record id"},
    "date": {"date", "transaction date", "txn date", "value date", "payment date"},
    "postedDate": {"posted date", "posting date", "post date", "settlement date", "settled on"},
    "amount": {"amount", "amt", "transaction amount", "txn amount", "value", "net amount", "amount inr"},
    "debit": {"debit", "withdrawal", "withdrawal amount", "dr", "paid out"},
    "credit": {"credit", "deposit", "deposit amount", "cr", "paid in"},
    "description": {"description", "narration", "details", "particulars", "memo", "remarks", "note"},
    "reference": {"reference", "ref", "ref no", "ref number", "reference no", "reference number", "utr", "cheque no", "chq no", "reference id"},
    "counterparty": {"counterparty", "payee", "payer", "party", "customer", "merchant", "vendor", "beneficiary"},
    "currency": {"currency", "ccy", "curr", "currency code"},
    "type": {"type", "transaction type", "txn type", "entry type"},
    "status": {"status", "state"},
}

_HEADER_CLEANUP = re.compile(r"[\s_\-]+")

# Fields that must survive normalization for a row to be usable.
REQUIRED_FIELDS = ("date",)


def normalize_header(header: str) -> str:
    return _HEADER_CLEANUP.sub(" ", header.strip().lower()).strip()


@dataclass
class ExtractedFile:
    """Result of extraction, pre-normalization."""

    records: list[dict] = field(default_factory=list)  # original rows, as parsed
    format_name: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.records) == 0


def resolve_fields(row: dict) -> dict:
    """Map a raw row onto canonical keys via FIELD_ALIASES. Values are kept
    exactly as extracted (normalization happens later)."""
    resolved: dict = {}
    for key, value in row.items():
        if key is None:
            continue
        header = normalize_header(str(key))
        text = str(value).strip() if value is not None else ""
        matched = False
        for canonical, aliases in FIELD_ALIASES.items():
            if header in aliases:
                resolved[canonical] = text
                matched = True
                break
        if not matched and text != "":
            # Unknown columns ride along inside metadata at normalization.
            resolved.setdefault("_extra", {})[str(key)] = text
    return resolved


def canonical_records_json(resolved_rows: list[dict]) -> str:
    """Deterministic serialization used by the file checksum."""
    return json.dumps(
        [{k: v for k, v in sorted(row.items())} for row in resolved_rows],
        sort_keys=True,
        separators=(",", ":"),
    )


def extract_csv(content: bytes) -> ExtractedFile:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidFileError("The CSV file must be UTF-8 encoded.") from None

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise InvalidFileError("The CSV file has no header row.")

    headers = {normalize_header(h) for h in reader.fieldnames if h}
    known = set()
    for aliases in FIELD_ALIASES.values():
        known |= aliases
    recognized = headers & known
    if not recognized:
        raise InvalidFileError(
            "None of the CSV columns could be recognized. Expected columns like "
            "date, amount or debit/credit, description, reference."
        )

    records: list[dict] = []
    for row in reader:
        cleaned = {k: v for k, v in row.items() if k is not None}
        records.append(cleaned)
    return ExtractedFile(records=records, format_name="csv")


def extract_jsonl(content: bytes) -> ExtractedFile:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidFileError("The JSONL file must be UTF-8 encoded.") from None
    records: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InvalidFileError(f"Invalid JSON on line {line_number}.") from exc
        if not isinstance(obj, dict):
            raise InvalidFileError(f"Line {line_number} is not a JSON object.")
        records.append(obj)
    return ExtractedFile(records=records, format_name="jsonl")


def extract(content: bytes, file_name: str, mime_type: str | None) -> ExtractedFile:
    name = (file_name or "").lower()
    if name.endswith(".csv") or (mime_type and "csv" in mime_type):
        return extract_csv(content)
    if name.endswith(".jsonl") or name.endswith(".ndjson") or (
        mime_type and ("json" in mime_type and "ld" in name)
    ):
        return extract_jsonl(content)
    # Fall back to sniffing: JSONL lines all start with '{'.
    sample = content[:512].lstrip()
    if sample.startswith(b"{"):
        return extract_jsonl(content)
    return extract_csv(content)
