from decimal import Decimal

import pytest

from app.services.normalization.money import (
    MoneyError,
    absolute,
    currency_exponent,
    money_to_str,
    parse_amount,
    quantize_for_currency,
    validate_currency,
)


def test_parse_exact_decimals_no_float_drift():
    assert parse_amount("5000.10") == Decimal("5000.10")
    assert parse_amount("0.01") == Decimal("0.01")
    # float 0.1+0.2 problem must not appear through the str() path
    assert parse_amount(0.1) == Decimal("0.1")
    assert parse_amount(0.2) == Decimal("0.2")


def test_parse_strips_separators_and_symbols():
    assert parse_amount("  ₹5,000.50 ") == Decimal("5000.50")
    assert parse_amount("$1,234.00") == Decimal("1234.00")
    assert parse_amount("-250") == Decimal("-250")


def test_parse_rejects_garbage():
    with pytest.raises(MoneyError):
        parse_amount("abc")
    with pytest.raises(MoneyError):
        parse_amount(None)
    with pytest.raises(MoneyError):
        parse_amount(True)
    with pytest.raises(MoneyError):
        parse_amount(float("inf"))


def test_quantize_respects_minor_units():
    assert quantize_for_currency(Decimal("100.999"), "INR") == Decimal("101.00")
    assert quantize_for_currency(Decimal("100.456"), "USD") == Decimal("100.46")
    assert quantize_for_currency(Decimal("1234.56"), "JPY") == Decimal("1235")
    assert currency_exponent("JPY") == 0
    assert currency_exponent("BHD") == 3


def test_validate_currency_normalizes_and_rejects():
    assert validate_currency("inr") == "INR"
    assert validate_currency(" usd ") == "USD"
    with pytest.raises(MoneyError):
        validate_currency("IN")
    with pytest.raises(MoneyError):
        validate_currency("INRX")
    with pytest.raises(MoneyError):
        validate_currency("123")
    with pytest.raises(MoneyError):
        validate_currency("XYZ")  # well-formed but unknown


def test_money_to_str_is_lossless():
    assert money_to_str(Decimal("5000.00")) == "5000.00"
    assert money_to_str(Decimal("0.10")) == "0.10"
    assert money_to_str(None) is None


def test_absolute():
    assert absolute(Decimal("-5.00")) == Decimal("5.00")
    assert absolute(Decimal("5.00")) == Decimal("5.00")
