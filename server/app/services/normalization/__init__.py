"""Normalization layer: converts source-specific representations into the
canonical transaction structure. See services/normalization modules."""

from .dates import DateError, days_between, from_utc_midnight, parse_date_value, parse_datetime_value, to_utc_midnight
from .fingerprint import compute_file_checksum, compute_fingerprint, compute_record_hash
from .money import (
    MoneyError,
    absolute,
    currency_exponent,
    money_to_str,
    parse_amount,
    quantize_for_currency,
    validate_currency,
)
from .text import (
    contains_similarity,
    jaccard_similarity,
    normalize_counterparty,
    normalize_reference,
    normalize_text,
    tokenize,
)

__all__ = [
    "DateError",
    "days_between",
    "from_utc_midnight",
    "parse_date_value",
    "parse_datetime_value",
    "to_utc_midnight",
    "compute_file_checksum",
    "compute_fingerprint",
    "compute_record_hash",
    "MoneyError",
    "absolute",
    "currency_exponent",
    "money_to_str",
    "parse_amount",
    "quantize_for_currency",
    "validate_currency",
    "contains_similarity",
    "jaccard_similarity",
    "normalize_counterparty",
    "normalize_reference",
    "normalize_text",
    "tokenize",
]
