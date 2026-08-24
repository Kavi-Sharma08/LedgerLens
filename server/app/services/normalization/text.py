"""Deterministic text normalization for financial strings.

Principles:
- Normalization exists only to make comparison fair. Original values are
  always preserved alongside their normalized forms.
- Rules are conservative: they remove formatting noise (case, punctuation,
  repeated whitespace) and well-understood legal-suffix boilerplate, but never
  information that could carry reconciliation signal.
"""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)

# Tokens that add no identity to a reference string ("Ref: NEFT1234" and
# "NEFT1234" must compare equal).
REFERENCE_STOPWORDS = frozenset(
    {"REF", "REFS", "REFERENCE", "REFNO", "NO", "NBR", "NUM", "NUMBER", "ID"}
)

# Legal-entity suffixes stripped from counterparties so "ABC Pvt Ltd",
# "ABC PRIVATE LIMITED" and "ABC PVT. LTD." normalize to the same tokens.
COUNTERPARTY_SUFFIXES = frozenset(
    {
        "PVT", "PRIVATE", "PTY", "LTD", "LIMITED", "LLP", "LLC", "INC",
        "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "PLC",
        "GMBH", "AG", "SA", "NV", "BV", "OPC",
    }
)


def normalize_text(value: str | None) -> str | None:
    """Lowercase, strip accents/punctuation, collapse whitespace.

    "  PAYMENT - ABC LTD  " -> "payment abc ltd"
    """
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value)
    text = _PUNCTUATION.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip().lower()
    return text or None


def tokenize(value: str | None) -> list[str]:
    """Split normalized text into non-empty tokens."""
    normalized = normalize_text(value)
    if not normalized:
        return []
    return normalized.split(" ")


def normalize_reference(value: str | None) -> str | None:
    """Canonical reference form: uppercase alnum tokens concatenated minus
    generic labels. Whitespace/punctuation inside a reference is formatting
    noise, never identity ("UTR 77" and "UTR-77" are the same UTR).

    "NEFT-1234"   -> "NEFT1234"
    "Ref: NEFT1234" -> "NEFT1234"
    "inv 2091"    -> "INV2091"
    """
    if value is None:
        return None
    tokens = [
        re.sub(r"[^0-9a-zA-Z]", "", token)
        for token in tokenize(value)
    ]
    kept = [t.upper() for t in tokens if t and t.upper() not in REFERENCE_STOPWORDS]
    if not kept:
        return None
    return "".join(kept)


def normalize_counterparty(value: str | None) -> str | None:
    """Normalized counterparty without legal suffixes.

    "ABC Pvt. Ltd." -> "abc"
    """
    if value is None:
        return None
    tokens = [
        t for t in tokenize(value)
        if t.upper() not in COUNTERPARTY_SUFFIXES
    ]
    if not tokens:
        return None
    return " ".join(tokens)


def jaccard_similarity(a: list[str], b: list[str]) -> float:
    """Token-set overlap in [0, 1]. Explainable and order-insensitive, so
    "payment abc ltd" vs "abc ltd payment" scores 1.0."""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    intersection = len(set_a & set_b)
    if intersection == 0:
        return 0.0
    union = len(set_a | set_b)
    return intersection / union


def contains_similarity(sub: list[str], sup: list[str]) -> bool:
    """True when every token of `sub` appears in `sup` (subset relation)."""
    return bool(sub) and set(sub).issubset(set(sup))
