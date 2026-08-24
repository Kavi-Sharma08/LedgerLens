"""End-to-end behaviour verification of the matching engine against the
deterministic synthetic dataset + its pinned ground truth."""

import pytest

from app.models.enums import ExceptionReason
from app.services.matching.config import DEFAULT_MATCHING_CONFIG
from app.services.matching.engine import reconcile
from app.synthetic.dataset import (
    all_records,
    bank_records,
    gateway_records,
)
from app.synthetic.ground_truth import GROUND_TRUTH, expected_for

from .conftest import WORKSPACE_ID, spec_to_txn


def _build():
    from bson import ObjectId

    bank_id, gateway_id = ObjectId(), ObjectId()
    bank_txns = [spec_to_txn(r, WORKSPACE_ID, bank_id) for r in bank_records()]
    gateway_txns = [spec_to_txn(r, WORKSPACE_ID, gateway_id) for r in gateway_records()]
    return bank_txns, gateway_txns


def test_dataset_is_large_and_ids_unique():
    records = all_records()
    assert len(records) >= 100
    rids = [r.rid for r in records if r.rid]
    assert len(rids) == len(set(rids))


@pytest.fixture(scope="module")
def reconciled():
    bank_txns, gateway_txns = _build()
    result = reconcile(bank_txns, gateway_txns)
    by_rid = {d.primary.source_record_id: d for d in result.decisions}
    return result, by_rid


def test_every_ground_truth_entry_holds(reconciled):
    result, by_rid = reconciled

    for entry in GROUND_TRUTH:
        decision = by_rid.get(entry["bank"])
        assert decision is not None, f"missing decision for {entry['bank']}"
        actual = decision.status.value
        assert actual == entry["expectedStatus"], (
            f"{entry['bank']} ({entry['reason']}): expected "
            f"{entry['expectedStatus']}, got {actual}"
        )

        if entry["expectedStatus"] in ("MATCHED", "LIKELY_MATCH"):
            selected = sorted(t.source_record_id for t in decision.selected)
            assert selected == sorted(entry["others"]), (
                f"{entry['bank']} paired with {selected}, expected {entry['others']}"
            )


def test_ambiguity_preserves_all_twins_as_evidence(reconciled):
    _, by_rid = reconciled
    for entry in (expected_for("B-AM-01"), expected_for("B-AM-02")):
        decision = by_rid[entry["bank"]]
        assert decision.status.value == "AMBIGUOUS"
        plausible_partners = {
            pair.transaction_b.source_record_id for pair in decision.candidates
            if pair.score >= DEFAULT_MATCHING_CONFIG.likely_match_threshold
        }
        assert set(entry["others"]) <= plausible_partners


def test_exception_reasons_are_precise(reconciled):
    _, by_rid = reconciled

    def reasons_of(rid):
        return {e.reason_code for e in by_rid[rid].exceptions}

    assert ExceptionReason.POSSIBLE_FEE in reasons_of("B-FE-01")
    assert ExceptionReason.STATUS_CONFLICT in reasons_of("B-PD-01")
    assert ExceptionReason.UNSUPPORTED_CURRENCY in reasons_of("B-CC-01")
    assert ExceptionReason.UNSUPPORTED_CURRENCY in reasons_of("B-CC-02")
    assert ExceptionReason.FAILED_TRANSACTION in reasons_of("B-FL-01")
    assert ExceptionReason.ZERO_AMOUNT in reasons_of("B-ZR-01")


def test_stats_are_consistent_with_decisions(reconciled):
    result, by_rid = reconciled
    stats = result.stats

    counts = {"MATCHED": 0, "LIKELY_MATCH": 0, "AMBIGUOUS": 0, "UNMATCHED": 0}
    for decision in result.decisions:
        if decision.status.value in counts:
            counts[decision.status.value] += 1

    assert stats["matchedCount"] == counts["MATCHED"]
    assert stats["likelyMatchCount"] == counts["LIKELY_MATCH"]
    assert stats["ambiguousCount"] == counts["AMBIGUOUS"]
    assert stats["unmatchedCount"] == counts["UNMATCHED"] + len(result.leftover_b)
    assert stats["exceptionCount"] >= 6  # fee x3, status, currency x2, failed, zero


def test_reconciliation_is_repeatable_byte_for_byte(reconciled):
    result, _ = reconciled
    again_bank, again_gw = _build()
    replayed = reconcile(again_bank, again_gw)

    assert [(d.primary.source_record_id, d.status.value, str(d.confidence))
            for d in result.decisions] == \
           [(d.primary.source_record_id, d.status.value, str(d.confidence))
            for d in replayed.decisions]
    assert result.stats == replayed.stats


def test_gateway_side_leftovers_include_known_lonely_records(reconciled):
    result, _ = reconciled
    leftovers = {t.source_record_id for t in result.leftover_b}
    # Gateway-only unmatched tail + split legs + zero record remain.
    assert "G-UM-01" in leftovers
    assert "G-SP-01A" in leftovers
    assert "G-SP-01B" in leftovers
    assert "G-ZR-01" in leftovers
