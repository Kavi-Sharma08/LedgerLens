"""Deterministic reconciliation engine (v1: pairwise, explainable).

Design constraints (see docs/reconciliation-engine.md):

- PURE: no MongoDB, no network, no clock reads. Given identical inputs and
  configuration it always produces identical output -> fully unit-testable.
- Deterministic ordering everywhere: inputs are sorted by
  (date, amount, id); candidate lists are sorted by (-score, partner id).
- Greedy consumption: once a B-side transaction is selected by a
  MATCHED/LIKELY_MATCH decision it cannot be re-selected by a later A-side
  transaction. Because A is processed in deterministic order, results are
  reproducible even though assignment order matters (documented limitation;
  global optimization arrives with many-to-one support).
- The engine classifies; it does NOT persist. services/reconciliation.py
  turns ReconciliationResult into Mongo documents.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from ...models.enums import (
    ExceptionReason,
    MatchType,
    ReconciliationStatus,
    TransactionStatus,
    TransactionType,
)
from ...models.transaction import Transaction
from ..normalization.dates import days_between
from .config import DEFAULT_MATCHING_CONFIG, MatchingConfig
from . import scorers

_ZERO = Decimal("0")
_ONE = Decimal("1")

_BLOCKING_STATUSES = {TransactionStatus.FAILED.value, TransactionStatus.CANCELLED.value}

# Type pairs that describe different economic events and must not auto-match.
_REFUND_CONFLICT_WITH = {TransactionType.SALE.value, TransactionType.PAYMENT.value}


@dataclass
class ScoredPair:
    """A scored candidate pair — pure evidence."""

    transaction_a: Transaction
    transaction_b: Transaction
    score: Decimal
    breakdown: dict = field(default_factory=dict)
    reasons: list = field(default_factory=list)


@dataclass
class ExceptionItem:
    """Investigation item produced by the engine (persisted by the service)."""

    transaction_ids: list
    reason_code: ExceptionReason
    detail: str


@dataclass
class GroupDecision:
    """Outcome for one A-side transaction against the B side."""

    primary: Transaction
    status: ReconciliationStatus
    candidates: list = field(default_factory=list)   # every considered pair
    selected: list = field(default_factory=list)     # chosen partners (if any)
    match_type: MatchType | None = None
    confidence: Decimal = _ZERO
    evidence: dict = field(default_factory=dict)
    exceptions: list = field(default_factory=list)


@dataclass
class ReconciliationResult:
    decisions: list = field(default_factory=list)
    leftover_b: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def exceptions(self) -> list:
        items = []
        for decision in self.decisions:
            items.extend(decision.exceptions)
        return items


def reconcile(
    transactions_a: list[Transaction],
    transactions_b: list[Transaction],
    config: MatchingConfig = DEFAULT_MATCHING_CONFIG,
) -> ReconciliationResult:
    """Reconcile two transaction sets. See module docstring for semantics."""
    ordered_a = _deterministic_sort(transactions_a)
    ordered_b = _deterministic_sort(transactions_b)

    pool = _index_by_currency(ordered_b, config)
    consumed: set = set()

    decisions: list[GroupDecision] = []

    for txn_a in ordered_a:
        decision = _process_one(txn_a, pool, consumed, config)
        decisions.append(decision)
        if decision.status in (ReconciliationStatus.MATCHED, ReconciliationStatus.LIKELY_MATCH):
            consumed.update(t.id for t in decision.selected)

    leftover_b = [t for t in ordered_b if t.id not in consumed]

    return ReconciliationResult(
        decisions=decisions,
        leftover_b=leftover_b,
        stats=_compute_stats(decisions, leftover_b),
    )


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _deterministic_sort(transactions: list[Transaction]) -> list[Transaction]:
    return sorted(
        transactions,
        key=lambda t: (
            t.transaction_date,
            t.amount,
            str(t.id),
        ),
    )


def _bucket_of(amount: Decimal, config: MatchingConfig) -> int:
    return int((amount / config.amount_bucket_value).to_integral_value(rounding=ROUND_FLOOR))


def _bucket_span(amount: Decimal, config: MatchingConfig) -> int:
    """How many amount buckets a fee-plausible partner can be away.

    The fee band is RELATIVE (2% of the larger amount), so for large amounts
    it can span several fixed-width buckets (e.g. 7840 vs 8000 straddles
    buckets 78 and 80). For b > a, diff <= a*rel/(1-rel) follows from
    diff <= b*rel; combined with the absolute floor this gives an exact,
    bounded reach. Blocking must never lose a candidate that scoring would
    accept."""
    rel = min(config.fee_relative_tolerance, Decimal("0.50"))
    reach = max(
        config.fee_absolute_tolerance,
        amount * rel / (_ONE - rel),
    )
    return int((reach / config.amount_bucket_value).to_integral_value(rounding=ROUND_CEILING))


def _index_by_currency(
    transactions: list[Transaction], config: MatchingConfig
) -> dict[str, dict[int, list[Transaction]]]:
    """Blocking structure: currency -> amount bucket -> transactions.

    Candidate generation probes every bucket within the fee-plausible reach
    of the A-side amount (see `_bucket_span`), so no pair that scoring could
    accept is lost to blocking."""
    index: dict[str, dict[int, list[Transaction]]] = {}
    for txn in transactions:
        if txn.status in _BLOCKING_STATUSES:
            continue  # failed/cancelled records are never matchable partners
        buckets = index.setdefault(txn.currency, {})
        buckets.setdefault(_bucket_of(txn.amount, config), []).append(txn)
    return index


def _candidate_transactions(
    txn_a: Transaction, pool: dict[str, dict[int, list[Transaction]]], config: MatchingConfig
) -> list[Transaction]:
    same_currency = pool.get(txn_a.currency, {})
    base = _bucket_of(txn_a.amount, config)
    span = _bucket_span(txn_a.amount, config)
    nearby: list[Transaction] = []
    seen = set()
    for bucket in range(base - span, base + span + 1):
        for candidate in same_currency.get(bucket, []):
            if candidate.id in seen:
                continue
            seen.add(candidate.id)
            if days_between(txn_a.transaction_date, candidate.transaction_date) <= config.candidate_date_window_days:
                nearby.append(candidate)
    return _deterministic_sort(nearby)


def _score_pair(txn_a: Transaction, txn_b: Transaction, config: MatchingConfig) -> ScoredPair:
    breakdown: dict[str, Decimal] = {}
    reasons: list[str] = []

    amount_s, amount_notes = scorers.amount_score(txn_a.amount, txn_b.amount, config)
    breakdown["amountScore"] = amount_s
    reasons.extend(amount_notes)

    days = days_between(txn_a.transaction_date, txn_b.transaction_date)
    date_s, date_notes = scorers.date_score(days, config)
    breakdown["dateScore"] = date_s
    reasons.extend(date_notes)

    weights = {
        "amountScore": config.weight_amount,
        "dateScore": config.weight_date,
        "referenceScore": config.weight_reference,
        "counterpartyScore": config.weight_counterparty,
        "descriptionScore": config.weight_description,
    }

    # Missing data gets a neutral prior instead of weight redistribution:
    # sparse records lose confidence but never crash or score inflated.
    reference = scorers.reference_score(txn_a.reference, txn_b.reference)
    if reference is None:
        breakdown["referenceScore"] = config.missing_component_score
        reasons.append("reference_missing")
    else:
        breakdown["referenceScore"], notes = reference
        reasons.extend(notes)

    counterparty = scorers.counterparty_score(txn_a.counterparty, txn_b.counterparty)
    if counterparty is None:
        breakdown["counterpartyScore"] = config.missing_component_score
        reasons.append("counterparty_missing")
    else:
        breakdown["counterpartyScore"], notes = counterparty
        reasons.extend(notes)

    description = scorers.description_score(txn_a.description, txn_b.description)
    if description is None:
        breakdown["descriptionScore"] = config.missing_component_score
        reasons.append("description_missing")
    else:
        breakdown["descriptionScore"], notes = description
        reasons.extend(notes)

    score = scorers.weighted_composite(breakdown, weights)

    # Economic-event compatibility modifiers (recorded, never silent).
    score, type_reasons = _apply_type_compatibility(txn_a, txn_b, score)
    reasons.extend(type_reasons)

    return ScoredPair(
        transaction_a=txn_a,
        transaction_b=txn_b,
        score=score,
        breakdown=dict(breakdown),
        reasons=reasons,
    )


def _apply_type_compatibility(
    txn_a: Transaction, txn_b: Transaction, score: Decimal
) -> tuple[Decimal, list[str]]:
    type_a, type_b = txn_a.transaction_type, txn_b.transaction_type
    if not type_a or not type_b:
        return score, []
    if (
        (type_a == TransactionType.REVERSAL.value) != (type_b == TransactionType.REVERSAL.value)
    ):
        return (score * Decimal("0.40")).quantize(Decimal("0.0001")), ["reversal_type_mismatch"]
    refund_conflict = (
        (type_a == TransactionType.REFUND.value and type_b in _REFUND_CONFLICT_WITH)
        or (type_b == TransactionType.REFUND.value and type_a in _REFUND_CONFLICT_WITH)
    )
    if refund_conflict:
        return (score * Decimal("0.50")).quantize(Decimal("0.0001")), ["type_conflict_refund_vs_sale"]
    return score, []


def _corroboration(breakdown: dict) -> Decimal:
    """Best non-monetary identity evidence (reference/counterparty/description)."""
    components = [
        breakdown.get("referenceScore"),
        breakdown.get("counterpartyScore"),
        breakdown.get("descriptionScore"),
    ]
    present = [c for c in components if c is not None]
    return max(present) if present else _ZERO


def _has_status_conflict(txn_a: Transaction, txn_b: Transaction) -> bool:
    statuses = (txn_a.status, txn_b.status)
    return (
        TransactionStatus.PENDING.value in statuses
        and TransactionStatus.SETTLED.value in statuses
    )


def _cross_currency_alternative(
    txn_a: Transaction,
    others: list[Transaction],
    config: MatchingConfig,
) -> Transaction | None:
    """A different-currency record that otherwise looks like the same event."""
    for candidate in others:
        if candidate.currency == txn_a.currency:
            continue
        if candidate.status in _BLOCKING_STATUSES:
            continue
        if days_between(txn_a.transaction_date, candidate.transaction_date) > config.date_tolerance_days:
            continue
        diff = abs(txn_a.amount - candidate.amount)
        band = max(
            config.fee_absolute_tolerance,
            max(txn_a.amount, candidate.amount) * config.fee_relative_tolerance,
        )
        if diff <= band:
            return candidate
    return None


def _make_exception(
    transactions: list[Transaction], reason_code: ExceptionReason, detail: str
) -> ExceptionItem:
    return ExceptionItem(
        transaction_ids=[t.id for t in transactions],
        reason_code=reason_code,
        detail=detail,
    )


def _process_one(
    txn_a: Transaction,
    pool: dict[str, dict[int, list[Transaction]]],
    consumed: set,
    config: MatchingConfig,
) -> GroupDecision:
    # Hard exclusions first — these records are informational/broken and are
    # routed to investigation rather than matched.
    if txn_a.status in _BLOCKING_STATUSES:
        decision = GroupDecision(primary=txn_a, status=ReconciliationStatus.EXCEPTION)
        decision.exceptions.append(
            _make_exception([txn_a], ExceptionReason.FAILED_TRANSACTION,
                            f"Transaction has status {txn_a.status}; excluded from matching.")
        )
        return decision
    if txn_a.amount == _ZERO:
        decision = GroupDecision(primary=txn_a, status=ReconciliationStatus.EXCEPTION)
        decision.exceptions.append(
            _make_exception([txn_a], ExceptionReason.ZERO_AMOUNT,
                            "Zero-amount record requires review; never auto-matched.")
        )
        return decision

    candidates = [
        _score_pair(txn_a, partner, config)
        for partner in _candidate_transactions(txn_a, pool, config)
    ]
    candidates.sort(key=lambda pair: (-pair.score, str(pair.transaction_b.id)))

    available = [pair for pair in candidates if pair.transaction_b.id not in consumed]

    if not available:
        # Scan the full B pool across currencies for a same-looking record.
        all_others = [t for buckets in pool.values() for rows in buckets.values() for t in rows]
        alternative = _cross_currency_alternative(txn_a, all_others, config)
        decision = GroupDecision(
            primary=txn_a,
            status=ReconciliationStatus.EXCEPTION if alternative else ReconciliationStatus.UNMATCHED,
            candidates=candidates,
        )
        if alternative:
            decision.exceptions.append(
                _make_exception(
                    [txn_a, alternative],
                    ExceptionReason.UNSUPPORTED_CURRENCY,
                    f"Same-looking record found in {alternative.currency} but this record is "
                    f"{txn_a.currency}; cross-currency comparison is not supported yet.",
                )
            )
        return decision

    return _classify(txn_a, candidates, available, config)


def _classify(
    txn_a: Transaction,
    all_candidates: list[ScoredPair],
    available: list[ScoredPair],
    config: MatchingConfig,
) -> GroupDecision:
    top = available[0]
    runner_up = available[1] if len(available) > 1 else None

    # Ambiguity: another unconsumed candidate scores within the margin of the
    # leader while both clear the likely threshold -> refuse to choose.
    cluster = [
        pair
        for pair in available[1:]
        if pair.score >= config.likely_match_threshold
        and (top.score - pair.score) < config.ambiguous_margin
    ]
    if cluster:
        decision = GroupDecision(
            primary=txn_a,
            status=ReconciliationStatus.AMBIGUOUS,
            candidates=all_candidates,
            confidence=top.score,
            evidence={
                "scoreBreakdown": {k: str(v) for k, v in top.breakdown.items()},
                "reasons": ["multiple_equally_plausible_candidates"],
                "ambiguousPartnerIds": [str(pair.transaction_b.id) for pair in cluster],
            },
        )
        decision.exceptions.append(
            _make_exception(
                [txn_a] + [pair.transaction_b for pair in cluster],
                ExceptionReason.NEEDS_REVIEW,
                "Multiple equally plausible matches preserved for human/AI review.",
            )
        )
        return decision

    if top.score < config.likely_match_threshold:
        return GroupDecision(
            primary=txn_a,
            status=ReconciliationStatus.UNMATCHED,
            candidates=all_candidates,
            confidence=top.score,
            evidence={
                "scoreBreakdown": {k: str(v) for k, v in top.breakdown.items()},
                "reasons": ["best_candidate_below_likely_threshold"] + top.reasons,
            },
        )

    # Ceiling logic: conditions that downgrade an automatic MATCHED.
    ceiling = ReconciliationStatus.MATCHED
    reasons = list(top.reasons)
    exceptions: list[ExceptionItem] = []

    if _corroboration(top.breakdown) < config.min_corroboration:
        ceiling = ReconciliationStatus.LIKELY_MATCH
        reasons.append("insufficient_non_amount_evidence")

    if "amount_within_fee_band" in reasons:
        ceiling = ReconciliationStatus.LIKELY_MATCH
        reasons.append("possible_processing_fee")
        difference = abs(txn_a.amount - top.transaction_b.amount)
        exceptions.append(
            _make_exception(
                [txn_a, top.transaction_b],
                ExceptionReason.POSSIBLE_FEE,
                f"Amount difference of {difference} may represent a processing fee.",
            )
        )

    if _has_status_conflict(txn_a, top.transaction_b):
        ceiling = ReconciliationStatus.LIKELY_MATCH
        reasons.append("status_conflict_pending_vs_settled")
        exceptions.append(
            _make_exception(
                [txn_a, top.transaction_b],
                ExceptionReason.STATUS_CONFLICT,
                "Pending record paired with a settled record; confirm settlement.",
            )
        )

    margin_ok = (
        runner_up is None
        or (top.score - runner_up.score) >= config.ambiguous_margin
        or runner_up.score < config.likely_match_threshold
    )

    if top.score >= config.exact_match_threshold and margin_ok:
        status = ReconciliationStatus.MATCHED
    else:
        status = ReconciliationStatus.LIKELY_MATCH
    if status == ReconciliationStatus.MATCHED and ceiling == ReconciliationStatus.LIKELY_MATCH:
        status = ReconciliationStatus.LIKELY_MATCH

    is_exact = (
        top.breakdown.get("amountScore") == _ONE
        and top.breakdown.get("dateScore") == _ONE
        and top.breakdown.get("referenceScore") == _ONE
    )
    match_type = MatchType.EXACT if (is_exact and status == ReconciliationStatus.MATCHED) else MatchType.FUZZY

    direction_note = (
        "directions_agree"
        if txn_a.direction == top.transaction_b.direction
        else "directions_differ_by_source_semantics"
    )

    return GroupDecision(
        primary=txn_a,
        status=status,
        candidates=all_candidates,
        selected=[top.transaction_b],
        match_type=match_type,
        confidence=top.score,
        evidence={
            "scoreBreakdown": {k: str(v) for k, v in top.breakdown.items()},
            "reasons": reasons + [direction_note],
            "tolerancesUsed": {
                "dateToleranceDays": config.date_tolerance_days,
                "feeAbsolute": str(config.fee_absolute_tolerance),
                "feeRelative": str(config.fee_relative_tolerance),
            },
        },
        exceptions=exceptions,
    )


def _compute_stats(decisions: list[GroupDecision], leftover_b: list[Transaction]) -> dict:
    counts = {
        "matchedCount": 0,
        "likelyMatchCount": 0,
        "ambiguousCount": 0,
        "unmatchedCount": len(leftover_b),
        "exceptionCount": 0,
    }
    for decision in decisions:
        if decision.status == ReconciliationStatus.MATCHED:
            counts["matchedCount"] += 1
        elif decision.status == ReconciliationStatus.LIKELY_MATCH:
            counts["likelyMatchCount"] += 1
        elif decision.status == ReconciliationStatus.AMBIGUOUS:
            counts["ambiguousCount"] += 1
        elif decision.status == ReconciliationStatus.UNMATCHED:
            counts["unmatchedCount"] += 1
        # Every investigation item is persisted regardless of which status its
        # decision carries (fee/status conflicts attach to LIKELY_MATCH,
        # ambiguity reviews to AMBIGUOUS), so the stat reflects reality.
        counts["exceptionCount"] += len(decision.exceptions)
    counts["totalTransactions"] = sum(counts.values())
    return counts
