"""Component scorers for deterministic matching.

Each scorer returns (score, notes):
  score  -- Decimal in [0, 1], or None when the component cannot be compared
            because data is missing on either side. Missing components are
            excluded from the weighted composite (their weight is
            redistributed), so sparse records degrade gracefully instead of
            crashing or being unfairly punished twice.
  notes  -- human-readable evidence strings preserved on candidates/matches.

All functions are pure and order-independent -> fully deterministic.
"""

from decimal import Decimal
from difflib import SequenceMatcher

from ..normalization.text import (
    contains_similarity,
    jaccard_similarity,
    normalize_counterparty,
    normalize_reference,
    tokenize,
)
from .config import MatchingConfig

_ONE = Decimal("1")
_ZERO = Decimal("0")

# Band scores for amount proximity inside the fee tolerance.
_FEE_BAND_START = Decimal("0.85")
_FEE_BAND_END = Decimal("0.60")
# Decay ceiling beyond the fee band (decays linearly to zero across a span of
# BAND_PENALTY_SPAN multiples of the band width).
_OVER_BAND_CEILING = Decimal("0.30")
_BAND_PENALTY_SPAN = Decimal("9")

# Reference/counterparty partial-match bonuses.
_SUBSET_SCORE = Decimal("0.90")


def amount_score(amount_a: Decimal, amount_b: Decimal, config: MatchingConfig) -> tuple[Decimal, list[str]]:
    """Amounts are equal-precision Decimals; currency equality is enforced by
    the engine before scoring."""
    diff = abs(amount_a - amount_b)
    if diff == 0:
        return _ONE, []

    band = max(config.fee_absolute_tolerance, max(amount_a, amount_b) * config.fee_relative_tolerance)
    if diff <= band:
        # Linear decay across the fee band: near-exact still strong, band
        # edge lands at _FEE_BAND_END.
        position = diff / band if band > 0 else _ONE
        score = _FEE_BAND_START - (_FEE_BAND_START - _FEE_BAND_END) * position
        return (
            score.quantize(Decimal("0.0001")),
            ["amount_within_fee_band"],
        )

    over = float(diff / band)
    fraction_past = min(1.0, (over - 1.0) / float(_BAND_PENALTY_SPAN))
    score = _OVER_BAND_CEILING * (_ONE - Decimal(str(fraction_past)))
    return score.quantize(Decimal("0.0001")), ["amount_mismatch"]


def date_score(days_apart: int, config: MatchingConfig) -> tuple[Decimal, list[str]]:
    """Same day strongest, +/-1 day high, decaying to zero at the tolerance
    edge; beyond tolerance the component contributes nothing."""
    if days_apart == 0:
        return _ONE, []
    if days_apart == 1:
        return Decimal("0.90"), []
    tolerance = max(1, config.date_tolerance_days)
    if days_apart > tolerance:
        return _ZERO, ["date_outside_tolerance"]
    step = Decimal("0.20")
    score = Decimal("0.90") - step * (days_apart - 1)
    return max(score, _ZERO), []


def reference_score(reference_a: str | None, reference_b: str | None) -> tuple[Decimal, list[str]] | None:
    """Exact-after-normalization beats partial overlap; missing references
    make the whole component unavailable rather than wrong."""
    norm_a = normalize_reference(reference_a)
    norm_b = normalize_reference(reference_b)
    if not norm_a or not norm_b:
        return None
    if norm_a == norm_b:
        return _ONE, []
    token_overlap = Decimal(str(round(jaccard_similarity(tokenize(norm_a), tokenize(norm_b)), 4)))
    sequence_ratio = Decimal(str(round(SequenceMatcher(None, norm_a, norm_b).ratio(), 4)))
    subset = contains_similarity(
        [t.upper() for t in tokenize(norm_a)], [t.upper() for t in tokenize(norm_b)]
    ) or contains_similarity(
        [t.upper() for t in tokenize(norm_b)], [t.upper() for t in tokenize(norm_a)]
    )
    best = max(token_overlap, sequence_ratio)
    if subset and best < _SUBSET_SCORE:
        best = _SUBSET_SCORE
    return best, ["reference_partial"]


def description_score(description_a: str | None, description_b: str | None) -> tuple[Decimal, list[str]] | None:
    """Token-set Jaccard on normalized text: order-insensitive, so
    "PAYMENT ABC LTD" vs "ABC LTD PAYMENT" scores 1.0."""
    tokens_a = tokenize(description_a)
    tokens_b = tokenize(description_b)
    if not tokens_a or not tokens_b:
        return None
    similarity = jaccard_similarity(tokens_a, tokens_b)
    return Decimal(str(round(similarity, 4))), []


def counterparty_score(counterparty_a: str | None, counterparty_b: str | None) -> tuple[Decimal, list[str]] | None:
    """Suffix-stripped token similarity ("ABC Pvt Ltd" ~ "ABC PRIVATE LIMITED")."""
    norm_a = normalize_counterparty(counterparty_a)
    norm_b = normalize_counterparty(counterparty_b)
    if not norm_a or not norm_b:
        return None
    tokens_a, tokens_b = norm_a.split(" "), norm_b.split(" ")
    if norm_a == norm_b:
        return _ONE, []
    if contains_similarity(tokens_a, tokens_b) or contains_similarity(tokens_b, tokens_a):
        return _SUBSET_SCORE, []
    similarity = jaccard_similarity(tokens_a, tokens_b)
    return Decimal(str(round(similarity, 4))), []


def weighted_composite(
    scores: dict[str, Decimal],
    weights: dict[str, Decimal],
) -> Decimal:
    """Weighted average over the provided components.

    The engine always supplies all five components (missing data arrives as a
    neutral prior from MatchingConfig.missing_component_score), so the active
    weight is normally 1.00. Dividing by the active weight keeps this function
    safe if callers ever pass partial component sets. Deterministic given
    identical inputs."""
    active_weight = sum(weights[name] for name in scores)
    if active_weight == 0 or not scores:
        return _ZERO
    total = sum(scores[name] * weights[name] for name in scores)
    return (total / active_weight).quantize(Decimal("0.0001"))
