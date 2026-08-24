from datetime import date, datetime, timezone

import pytest

from app.services.normalization.dates import (
    DateError,
    days_between,
    from_utc_midnight,
    parse_date_value,
    to_utc_midnight,
)


def test_iso_and_day_first_formats():
    assert parse_date_value("2026-08-10") == date(2026, 8, 10)
    assert parse_date_value("10/08/2026") == date(2026, 8, 10)   # day-first
    assert parse_date_value("10-08-2026") == date(2026, 8, 10)
    assert parse_date_value(date(2026, 1, 2)) == date(2026, 1, 2)


def test_datetime_inputs_take_calendar_date():
    ts = datetime(2026, 8, 10, 18, 30, tzinfo=timezone.utc)
    assert parse_date_value(ts) == date(2026, 8, 10)


def test_unparseable_dates_raise_safe_error():
    with pytest.raises(DateError):
        parse_date_value("not a date")
    with pytest.raises(DateError):
        parse_date_value("")
    with pytest.raises(DateError):
        parse_date_value(None)


def test_utc_midnight_roundtrip_preserves_calendar_semantics():
    original = date(2026, 3, 7)
    stored = to_utc_midnight(original)
    assert stored.tzinfo is not None
    assert from_utc_midnight(stored) == original
    # A +05:30 shift must never move the financial date.
    shifted = stored.isoformat()
    assert shifted.startswith("2026-03-07T00:00")


def test_days_between_is_symmetric():
    assert days_between(date(2026, 8, 10), date(2026, 8, 11)) == 1
    assert days_between(date(2026, 8, 11), date(2026, 8, 10)) == 1
    assert days_between(date(2026, 8, 10), date(2026, 8, 10)) == 0
