"""Date handling for financial records.

Rules:
- Date-only financial dates (most statements) keep calendar-date semantics.
  They are stored as UTC-midnight datetimes purely so MongoDB can range-query
  them; all domain logic compares `.date()` values, so no timezone shift can
  ever move a financial date to another day.
- True timestamps are normalized to UTC.
- Numeric day-first formats (10/08/2026 -> 10 Aug) are the convention for the
  Indian-market sources LedgerLens targets; ISO format is always tried first.
"""

from datetime import date, datetime, timezone

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)
_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
)


class DateError(ValueError):
    """Raised for unparseable financial dates."""


def parse_date_value(raw) -> date:
    """Parse a date/datetime/ISO-string into a calendar date."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise DateError("Date is required.")

    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw

    text = str(raw).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise DateError(f"Unsupported date format: {text[:32]}")


def parse_datetime_value(raw) -> datetime | None:
    """Parse a timestamp to aware UTC. Returns None for empty input."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text.replace("Z", "+0000") if fmt.endswith("%z") else text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    # Fall back to date parsing at UTC midnight.
    return datetime.combine(parse_date_value(text), datetime.min.time(), tzinfo=timezone.utc)


def to_utc_midnight(value: date | datetime) -> datetime:
    """Storage form: midnight UTC keeps Mongo range queries possible while
    preserving pure calendar semantics."""
    if isinstance(value, datetime):
        value = value.date()
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def from_utc_midnight(value: datetime | None) -> date | None:
    """Inverse of to_utc_midnight for document loading."""
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def days_between(a: date, b: date) -> int:
    return abs((a - b).days)
