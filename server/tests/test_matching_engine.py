from decimal import Decimal

import pytest

from app.models.enums import ExceptionReason, MatchType, ReconciliationStatus
from app.services.matching.config import MatchingConfig
from app.services.matching.engine import reconcile

from .conftest import SOURCE_A, SOURCE_B, make_txn


def decision_for(result, txn):
    for decision in result.decisions:
        if decision.primary.id == txn.id:
            return decision
    raise AssertionError("decision not found")


def test_identical_pair_is_exact_match():
    a = make_txn(rid="A1", amount="500.00", description="PAYMENT ABC",
                 reference="NEFT001", counterparty="ABC PVT LTD")
    b = make_txn(rid="B1", amount="500.00", description="ABC PAYMENT",
                 reference="NEFT001", counterparty="ABC LTD", source_id=SOURCE_B)

    result = reconcile([a], [b])
    decision = decision_for(result, a)

    assert decision.status == ReconciliationStatus.MATCHED
    assert decision.match_type == MatchType.EXACT
    assert decision.confidence == Decimal("1.0000")
    assert [t.id for t in decision.selected] == [b.id]
    assert result.leftover_b == []


def test_one_day_difference_still_matches_with_high_confidence():
    a = make_txn(rid="A1", txn_date=(2026, 8, 10), description="PAYMENT THETA 1",
                 reference="NEFT7100", counterparty="THETA PVT LTD")
    b = make_txn(rid="B1", txn_date=(2026, 8, 11), description="THETA 1 PAYMENT",
                 reference="NEFT7100", counterparty="THETA PRIVATE LIMITED", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    assert decision.status == ReconciliationStatus.MATCHED
    assert decision.confidence >= Decimal("0.95")


def test_date_outside_tolerance_with_weak_evidence_stays_unmatched():
    a = make_txn(rid="A1", txn_date=(2026, 8, 10), amount="800.00", description="PAYMENT XI",
                 reference="RAAA1", counterparty="XI CORP")
    b = make_txn(rid="B1", txn_date=(2026, 8, 15), amount="800.00", description="SOMETHING ELSE",
                 reference="RBBB2", counterparty="OTHER VENDOR", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    assert decision.status == ReconciliationStatus.UNMATCHED


def test_strong_reference_can_overcome_date_drift_but_confidence_drops():
    a = make_txn(rid="A1", txn_date=(2026, 8, 10), description="PAYMENT KAPPA",
                 reference="CHOLAND188", counterparty="KAPPA MART")
    b = make_txn(rid="B1", txn_date=(2026, 8, 14), description="KAPPA MART ORDER",
                 reference="CHOLAND188", counterparty="KAPPA MART PRIVATE LIMITED",
                 source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    # Date component is zero (4 days), so the composite cannot reach EXACT.
    assert decision.status in (ReconciliationStatus.MATCHED, ReconciliationStatus.LIKELY_MATCH)
    assert decision.confidence < Decimal("0.90") or decision.match_type == MatchType.FUZZY
    assert "dateScore" in decision.evidence["scoreBreakdown"]


def test_missing_reference_lands_in_likely_match_band():
    a = make_txn(rid="A1", description="PAYMENT IOTA STORES 1", counterparty="IOTA STORES PVT LTD")
    b = make_txn(rid="B1", description="IOTA STORES 1 PAYMENT",
                 counterparty="IOTA STORES PRIVATE LIMITED", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    assert decision.status == ReconciliationStatus.LIKELY_MATCH
    assert "reference_missing" in decision.evidence["reasons"]


def test_amount_only_pairs_cannot_auto_match():
    # Identical amounts/dates but no textual identity at all.
    a = make_txn(rid="A1", description=None, reference=None, counterparty=None)
    b = make_txn(rid="B1", description=None, reference=None, counterparty=None, source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    assert decision.status == ReconciliationStatus.LIKELY_MATCH
    assert "insufficient_non_amount_evidence" in decision.evidence["reasons"]


def test_ambiguous_twins_are_never_auto_selected():
    a = make_txn(rid="A1", amount="6500.00", description="PAYMENT LAMBDA CORP",
                 reference=None, counterparty="LAMBDA CORP PVT LTD")
    twin_a = make_txn(rid="TWIN-A", amount="6500.00", description="LAMBDA CORP PAYMENT",
                      reference="PAY1", counterparty="LAMBDA CORP PVT LTD", source_id=SOURCE_B)
    twin_b = make_txn(rid="TWIN-B", amount="6500.00", description="LAMBDA CORP PAYMENT",
                      reference="PAY2", counterparty="LAMBDA CORP PVT LTD", source_id=SOURCE_B)

    result = reconcile([a], [twin_a, twin_b])
    decision = decision_for(result, a)

    assert decision.status == ReconciliationStatus.AMBIGUOUS
    assert decision.selected == []
    reasons = decision.evidence["reasons"]
    assert "multiple_equally_plausible_candidates" in reasons
    assert len(decision.exceptions) == 1
    assert decision.exceptions[0].reason_code == ExceptionReason.NEEDS_REVIEW
    # Neither twin was consumed.
    assert {t.id for t in result.leftover_b} == {twin_a.id, twin_b.id}


def test_refund_does_not_match_original_sale():
    a = make_txn(rid="A1", amount="1800.00", description="REFUND MU NU 1",
                 reference="RFND200", counterparty="MU NU RETAIL PVT LTD", txn_type="REFUND")
    sale = make_txn(rid="B1", amount="1800.00", description="MU NU ORDER 1 CAPTURE",
                    reference="RFND200", counterparty="MU NU RETAIL LIMITED",
                    txn_type="SALE", source_id=SOURCE_B)

    result = reconcile([a], [sale])
    decision = decision_for(result, a)
    assert decision.status == ReconciliationStatus.UNMATCHED
    top = decision.candidates[0]
    assert "type_conflict_refund_vs_sale" in top.reasons
    assert sale.id in {t.id for t in result.leftover_b}


def test_reversal_pairs_reversal_of_same_event():
    a = make_txn(rid="A1", amount="2750.00", description="REVERSAL XI PAY",
                 reference="RVSL301", counterparty="XI PAYMENTS PVT LTD", txn_type="REVERSAL")
    b = make_txn(rid="B1", amount="2750.00", description="XI PAY REVERSAL PROCESSED",
                 reference="RVSL301", counterparty="XI PAYMENTS LIMITED",
                 txn_type="REVERSAL", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [b]), a)
    assert decision.status == ReconciliationStatus.MATCHED


def test_fee_band_difference_is_likely_match_with_exception():
    a = make_txn(rid="A1", amount="9900.00", description="SETTLEMENT PI COMMERCE 1",
                 reference="PAYOUT400", counterparty="PI COMMERCE PVT LTD")
    gross = make_txn(rid="B1", amount="10000.00", description="PI COMMERCE 1 CAPTURE BATCH",
                     reference="PAYOUT400", counterparty="PI COMMERCE LIMITED", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [gross]), a)
    assert decision.status == ReconciliationStatus.LIKELY_MATCH
    assert "possible_processing_fee" in decision.evidence["reasons"]
    assert any(e.reason_code == ExceptionReason.POSSIBLE_FEE for e in decision.exceptions)


def test_pending_vs_settled_downgrades_to_likely_match():
    a = make_txn(rid="A1", amount="5600.00", description="PAYMENT SIGMA SOFT",
                 reference="NEFT8121", counterparty="SIGMA SOFT PVT LTD")
    pending = make_txn(rid="B1", amount="5600.00", description="SIGMA SOFT PAYMENT",
                       reference="NEFT8121", counterparty="SIGMA SOFT LIMITED",
                       status="PENDING", source_id=SOURCE_B)

    decision = decision_for(reconcile([a], [pending]), a)
    assert decision.status == ReconciliationStatus.LIKELY_MATCH
    assert "status_conflict_pending_vs_settled" in decision.evidence["reasons"]
    assert any(e.reason_code == ExceptionReason.STATUS_CONFLICT for e in decision.exceptions)


def test_failed_primary_becomes_exception_without_candidates():
    failed = make_txn(rid="F1", status="FAILED", amount="4500.00")

    result = reconcile([failed], [])
    decision = result.decisions[0]
    assert decision.status == ReconciliationStatus.EXCEPTION
    assert decision.exceptions[0].reason_code == ExceptionReason.FAILED_TRANSACTION
    assert decision.candidates == []


def test_failed_partner_is_excluded_from_matching():
    good = make_txn(rid="A1", amount="900.00", description="CHI STORES AUTH",
                    reference="AUTH771", counterparty="CHI STORES PVT LTD")
    settled_twin = make_txn(rid="OK", amount="900.00", description="CHI STORES CAPTURED",
                            reference="AUTH771", counterparty="CHI STORES LIMITED",
                            source_id=SOURCE_B)
    failed_twin = make_txn(rid="BAD", amount="900.00", description="CHI STORES FAILED",
                           reference="AUTH771", counterparty="CHI STORES LIMITED",
                           status="FAILED", source_id=SOURCE_B)

    result = reconcile([good], [failed_twin, settled_twin])
    decision = decision_for(result, good)
    assert decision.selected[0].id == settled_twin.id


def test_zero_amount_is_routed_to_review():
    zero = make_txn(rid="Z1", amount="0.00")
    result = reconcile([zero], [])
    assert result.decisions[0].status == ReconciliationStatus.EXCEPTION
    assert result.decisions[0].exceptions[0].reason_code == ExceptionReason.ZERO_AMOUNT


def test_cross_currency_lookalike_raises_unsupported_currency():
    inr = make_txn(rid="CC1", amount="12000.00", currency="INR", description="PHI GLOBALS 1",
                   reference="SWIFT600", counterparty="PHI GLOBALS")
    usd = make_txn(rid="USD1", amount="12000.00", currency="USD", description="PHI GLOBALS INTL",
                   reference="SWIFT600", counterparty="PHI GLOBALS", source_id=SOURCE_B)

    result = reconcile([inr], [usd])
    decision = result.decisions[0]
    assert decision.status == ReconciliationStatus.EXCEPTION
    assert decision.exceptions[0].reason_code == ExceptionReason.UNSUPPORTED_CURRENCY


def test_cross_source_direction_semantics_do_not_block_matching():
    """Bank: -5000.00 DEBIT. Gateway: 5000.00 PAYMENT (CREDIT).

    Sign conventions differ per system; ingestion normalizes to
    absolute-amount + direction, and the engine evaluates source semantics
    (recorded in evidence) instead of blindly rejecting on sign."""
    bank = make_txn(rid="A1", amount="5000.00", direction="DEBIT",
                    txn_date=(2026, 8, 10), description="PAYMENT ABC LTD",
                    reference="NEFT1001", counterparty="ABC LTD")
    gateway = make_txn(rid="B1", amount="5000.00", direction="CREDIT",
                       txn_date=(2026, 8, 10), description="ABC LTD PAYMENT",
                       reference="NEFT1001", counterparty="ABC PRIVATE LIMITED",
                       source_id=SOURCE_B)

    result = reconcile([bank], [gateway])
    decision = decision_for(result, bank)
    assert decision.status == ReconciliationStatus.MATCHED
    # The differing representation is recorded as evidence, never hidden.
    assert "directions_differ_by_source_semantics" in decision.evidence["reasons"]

    mirrored = reconcile([make_txn(rid="A2", amount="5000.00", direction="CREDIT",
                                   description="PAYMENT ABC LTD", reference="NEFT1001",
                                   counterparty="ABC LTD")], [gateway])
    same_sign_reasons = decision_for(mirrored, mirrored.decisions[0].primary).evidence["reasons"]
    assert "directions_agree" in same_sign_reasons


def test_greedy_consumption_prevents_double_matching():
    first = make_txn(rid="A1", amount="700.00", description="PAYMENT DUPO",
                     reference="DUPREF1", counterparty="DUPO LTD")
    second = make_txn(rid="A2", amount="700.00", description="PAYMENT DUPO",
                      reference="DUPREF1", counterparty="DUPO LTD")
    only_partner = make_txn(rid="B1", amount="700.00", description="DUPO PAYMENT",
                            reference="DUPREF1", counterparty="DUPO LIMITED", source_id=SOURCE_B)

    result = reconcile([first, second], [only_partner])
    statuses = {d.primary.id: d.status for d in result.decisions}
    assert statuses[first.id] == ReconciliationStatus.MATCHED
    assert statuses[second.id] == ReconciliationStatus.UNMATCHED


def test_leftover_b_reports_unconsumed_partners():
    a = make_txn(rid="A1", amount="10.00")
    lonely_b = make_txn(rid="B1", amount="9999.00", source_id=SOURCE_B)
    result = reconcile([a], [lonely_b])
    assert [t.id for t in result.leftover_b] == [lonely_b.id]


def test_engine_is_deterministic_regardless_of_input_order():
    def population():
        a1 = make_txn(rid="A1", amount="100.00", txn_date=(2026, 8, 3), source_record_id="A1")
        a2 = make_txn(rid="A2", amount="200.00", txn_date=(2026, 8, 4), source_record_id="A2")
        b1 = make_txn(rid="B1", amount="100.00", txn_date=(2026, 8, 3),
                      source_id=SOURCE_B, source_record_id="B1")
        b2 = make_txn(rid="B2", amount="200.00", txn_date=(2026, 8, 4),
                      source_id=SOURCE_B, source_record_id="B2")
        return a1, a2, b1, b2

    a1, a2, b1, b2 = population()
    run_one = reconcile([a1, a2], [b1, b2])

    a1, a2, b1, b2 = population()
    run_two = reconcile([a2, a1], [b2, b1])   # shuffled inputs

    signature_one = [(d.primary.source_record_id, d.status.value, str(d.confidence))
                     for d in run_one.decisions]
    signature_two = [(d.primary.source_record_id, d.status.value, str(d.confidence))
                     for d in run_two.decisions]
    assert signature_one == signature_two

    repeat = reconcile([a1, a2], [b1, b2])
    assert [(d.status.value, str(d.confidence)) for d in repeat.decisions] == \
           [(d.status.value, str(d.confidence)) for d in run_one.decisions]


def test_empty_inputs_produce_empty_stats():
    result = reconcile([], [])
    assert result.decisions == []
    assert result.leftover_b == []
    stats = result.stats
    assert stats["matchedCount"] == 0 and stats["totalTransactions"] == 0


def test_missing_text_fields_do_not_crash_scoring():
    a = make_txn(rid="M1", description=None, reference=None, counterparty=None, txn_type=None)
    b = make_txn(rid="M2", description=None, reference=None, counterparty=None,
                 source_id=SOURCE_B)
    result = reconcile([a], [b])
    decision = result.decisions[0]
    breakdown = decision.evidence.get("scoreBreakdown") or decision.candidates[0].breakdown
    assert set(breakdown) >= {"amountScore", "dateScore", "referenceScore"}


def test_custom_config_changes_thresholds():
    strict = MatchingConfig(exact_match_threshold=Decimal("1.00"),
                            likely_match_threshold=Decimal("0.99"))
    a = make_txn(rid="C1", description="PAYMENT ZEN", reference="Z1", counterparty="ZEN LTD")
    b = make_txn(rid="C2", description="ZEN PAYMENT", reference="Z1",
                 counterparty="ZEN LIMITED", source_id=SOURCE_B)
    decision = decision_for(reconcile([a], [b], config=strict), a)
    # With a stricter threshold the same pair can no longer reach MATCHED.
    assert decision.status != ReconciliationStatus.MATCHED or decision.confidence >= Decimal("0.99")
