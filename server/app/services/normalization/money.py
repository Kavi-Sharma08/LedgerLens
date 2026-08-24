"""Money primitives.

Money is never a float. Parsing, validation and quantization happen here so
every layer (models, ingestion, matching) shares one precise implementation.

- Python side: decimal.Decimal
- MongoDB side: bson Decimal128 (handled in model to_document/from_document)
- API side: amounts are serialized as strings to keep JSON lossless
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bson.decimal128 import Decimal128

# Minor-unit exponents for currencies we may reasonably see. Anything not
# listed defaults to 2 decimals; exotic currencies can be added as needed.
CURRENCY_EXPONENTS = {
    "JPY": 0,
    "KRW": 0,
    "VND": 0,
    "CLP": 0,
    "BHD": 3,
    "JOD": 3,
    "KWD": 3,
    "OMR": 3,
    "TND": 3,
}
DEFAULT_EXPONENT = 2

# ISO-4217 codes this deployment is expected to handle. Validation is format +
# membership: an unknown but well-formed code is rejected with a clear error
# rather than silently treated as valid.
KNOWN_CURRENCIES = frozenset(
    {
        "INR", "USD", "EUR", "GBP", "AED", "AUD", "CAD", "CHF", "CNY",
        "SGD", "HKD", "JPY", "KRW", "NZD", "SEK", "NOK", "DKK", "PLN",
        "BHD", "JOD", "KWD", "OMR", "TND", "VND", "CLP", "ZAR", "BRL",
        "MXN", "TRY", "SAR", "QAR", "MYR", "THB", "IDR", "PHP",
    }
)


class MoneyError(ValueError):
    """Raised for malformed monetary input. Never leaks raw values into logs."""


def validate_currency(code: str) -> str:
    """Validate an ISO-style currency code; returns the normalized code."""
    if not isinstance(code, str):
        raise MoneyError("Currency must be a string.")
    normalized = code.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise MoneyError("Currency must be a 3-letter code (e.g. INR).")
    if normalized not in KNOWN_CURRENCIES:
        raise MoneyError(f"Unsupported currency code: {normalized}")
    return normalized


def currency_exponent(currency: str) -> int:
    return CURRENCY_EXPONENTS.get(validate_currency(currency), DEFAULT_EXPONENT)


def parse_amount(raw) -> Decimal:
    """Parse a monetary value from user/parser input into an exact Decimal.

    Accepts Decimal/int/float/str. Strings may contain commas and a leading
    currency symbol; the sign is preserved for the caller to interpret.
    Floats are converted through str() to avoid binary-float artifacts
    (e.g. float 0.1 -> Decimal('0.1'), not '0.1000000000000000055...').
    """
    if raw is None:
        raise MoneyError("Amount is required.")
    if isinstance(raw, bool):
        raise MoneyError("Amount must be a number.")
    if isinstance(raw, Decimal):
        value = raw
    elif isinstance(raw, int):
        value = Decimal(raw)
    elif isinstance(raw, float):
        value = Decimal(str(raw))
    elif isinstance(raw, str):
        cleaned = raw.strip().replace(",", "").replace("₹", "").replace("$", "")
        cleaned = cleaned.replace("€", "").replace("£", "")
        try:
            value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise MoneyError("Amount is not a valid number.") from exc
    else:
        raise MoneyError("Amount must be a number or numeric string.")

    if not value.is_finite():
        raise MoneyError("Amount must be finite.")
    return value


def quantize_for_currency(value: Decimal, currency: str) -> Decimal:
    """Quantize to the currency's minor unit using banker-safe rounding."""
    exponent = Decimal(1).scaleb(-currency_exponent(currency))
    return value.quantize(exponent, rounding=ROUND_HALF_UP)


def money_to_str(value: Decimal | None) -> str | None:
    """Lossless string form for API payloads ('5000.00', never 5000.0)."""
    if value is None:
        return None
    return format(value, "f")


def absolute(value: Decimal) -> Decimal:
    return -value if value < 0 else value


def decimal128(value) -> Decimal128:
    """Decimal -> BSON Decimal128 (None-safe)."""
    from bson.decimal128 import Decimal128

    if value is None:
        return None
    return Decimal128(value if isinstance(value, Decimal) else Decimal(str(value)))


def as_decimal(value):
    """BSON Decimal128 / numeric / string -> Decimal (None-safe)."""
    from bson.decimal128 import Decimal128

    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))
