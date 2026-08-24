"""Matching configuration.

All weights, thresholds and tolerances live here — no magic numbers anywhere
in the engine. The effective configuration is frozen into every
ReconciliationRun so historical results remain reproducible."""

from dataclasses import dataclass, field, fields, replace
from decimal import Decimal

# Version recorded on runs/matches. Bump whenever scoring semantics change.
ALGORITHM_VERSION = "ll-v1-pairwise"


def _d(value: str) -> Decimal:
    return Decimal(value)


@dataclass(frozen=True)
class MatchingConfig:
    """Deterministic, explainable matching parameters."""

    # Component weights (must sum to 1.00). Initial values per phase-2 spec;
    # tuned deliberately, not scattered through code.
    weight_amount: Decimal = _d("0.35")
    weight_date: Decimal = _d("0.20")
    weight_reference: Decimal = _d("0.20")
    weight_counterparty: Decimal = _d("0.15")
    weight_description: Decimal = _d("0.10")

    # Date behaviour: same day strongest, +/-1 high, decaying to the
    # tolerance edge, zero beyond it. Candidates are generated inside the
    # wider candidate window so low-date-score pairs still get evidence.
    date_tolerance_days: int = 3
    candidate_date_window_days: int = 10

    # Fee band: differences within max(abs floor, relative %) may be
    # processing fees -> LIKELY_MATCH + exception, never auto-MATCHED.
    fee_absolute_tolerance: Decimal = _d("1.00")
    fee_relative_tolerance: Decimal = _d("0.02")

    # Classification thresholds on the composite score.
    exact_match_threshold: Decimal = _d("0.90")
    likely_match_threshold: Decimal = _d("0.70")

    # When the top two candidates differ by less than this margin the pair
    # cluster is AMBIGUOUS instead of auto-selected.
    ambiguous_margin: Decimal = _d("0.05")

    # Minimum best non-amount/non-date component score required before an
    # automatic MATCHED is allowed. Prevents "amount-only" finalization.
    min_corroboration: Decimal = _d("0.50")

    # Neutral prior for components that cannot be compared because data is
    # missing on either side. Missing evidence must REDUCE confidence, not
    # inflate the remaining weights (which would reward sparse records).
    missing_component_score: Decimal = _d("0.45")

    # Candidate generation bucket width for amount blocking (adjacent
    # buckets are also probed, so boundary straddling is safe).
    amount_bucket_value: Decimal = _d("100.00")

    def to_dict(self) -> dict:
        return {
            f.name: (
                str(getattr(self, f.name))
                if isinstance(getattr(self, f.name), Decimal)
                else getattr(self, f.name)
            )
            for f in fields(self)
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "MatchingConfig":
        if not data:
            return cls()
        kwargs = {}
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            if isinstance(value, str) and f.type is Decimal:
                value = Decimal(value)
            kwargs[f.name] = value
        return cls(**kwargs)

    def with_overrides(self, **overrides) -> "MatchingConfig":
        return replace(self, **overrides)


DEFAULT_MATCHING_CONFIG = MatchingConfig()
