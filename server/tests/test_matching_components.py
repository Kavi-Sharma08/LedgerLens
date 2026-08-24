from decimal import Decimal

from app.services.matching import scorers
from app.services.matching.config import DEFAULT_MATCHING_CONFIG as CFG


def test_amount_score_exact():
    score, notes = scorers.amount_score(Decimal("100.00"), Decimal("100.00"), CFG)
    assert score == 1
    assert notes == []


def test_amount_score_decays_across_fee_band():
    # band = max(1.00, 2% of 100) = 2.00; diff 1.00 -> midpoint of the band.
    score, notes = scorers.amount_score(Decimal("101.00"), Decimal("100.00"), CFG)
    assert Decimal("0.60") < score < Decimal("0.85")
    assert "amount_within_fee_band" in notes


def test_amount_score_band_edge_hits_floor():
    # band = max(1.00 abs floor, 2% of 40 = 0.80) = 1.00; diff 1.00 == band.
    score, notes = scorers.amount_score(Decimal("41.00"), Decimal("40.00"), CFG)
    assert score == Decimal("0.6000")
    assert "amount_within_fee_band" in notes


def test_amount_score_beyond_band_decays_to_zero():
    mid, _ = scorers.amount_score(Decimal("42.00"), Decimal("40.00"), CFG)   # 2x band
    far, _ = scorers.amount_score(Decimal("45.00"), Decimal("40.00"), CFG)
    zero, notes = scorers.amount_score(Decimal("50.00"), Decimal("40.00"), CFG)
    assert Decimal("0") < mid < Decimal("0.30")
    assert far < mid
    assert zero == 0
    assert "amount_mismatch" in notes


def test_date_score_curve():
    assert scorers.date_score(0, CFG)[0] == 1
    assert scorers.date_score(1, CFG)[0] == Decimal("0.90")
    assert scorers.date_score(2, CFG)[0] == Decimal("0.70")
    assert scorers.date_score(3, CFG)[0] == Decimal("0.50")
    beyond, notes = scorers.date_score(4, CFG)
    assert beyond == 0
    assert "date_outside_tolerance" in notes


def test_reference_score_normalization_equality():
    score, _ = scorers.reference_score("NEFT-1234", "ref: NEFT 1234")
    assert score == 1


def test_reference_partial_scores_below_one():
    score, notes = scorers.reference_score("UTR5000", "UTR5999")
    assert 0 < score < 1
    assert "reference_partial" in notes


def test_reference_missing_returns_none():
    assert scorers.reference_score(None, "ABC123") is None
    assert scorers.reference_score("ABC123", "") is None
    assert scorers.reference_score(None, None) is None


def test_counterparty_suffix_equivalence():
    score, _ = scorers.counterparty_score("ABC Pvt Ltd", "ABC PRIVATE LIMITED")
    assert score == 1
    subset, _ = scorers.counterparty_score("Beta Industries", "Beta Industries LLP")
    assert subset == 1


def test_counterparty_different_parties_score_low():
    score, _ = scorers.counterparty_score("Alpha Traders Pvt Ltd", "Omega Retail Ltd")
    assert score < Decimal("0.50")


def test_counterparty_missing_returns_none():
    assert scorers.counterparty_score(None, "abc") is None


def test_description_jaccard_order_insensitive():
    score, _ = scorers.description_score("PAYMENT ABC LTD", "ABC LTD PAYMENT")
    assert score == 1


def test_description_partial_and_missing():
    partial, _ = scorers.description_score("payment beta industries inv 7712", "beta industries payment part")
    assert 0 < partial < 1
    assert scorers.description_score(None, "text") is None
    assert scorers.description_score("", "text") is None


def test_weighted_composite_full_weights():
    scores = {
        "amountScore": Decimal("1"),
        "dateScore": Decimal("1"),
        "referenceScore": Decimal("1"),
        "counterpartyScore": Decimal("1"),
        "descriptionScore": Decimal("1"),
    }
    weights = {
        "amountScore": CFG.weight_amount,
        "dateScore": CFG.weight_date,
        "referenceScore": CFG.weight_reference,
        "counterpartyScore": CFG.weight_counterparty,
        "descriptionScore": CFG.weight_description,
    }
    assert scorers.weighted_composite(scores, weights) == Decimal("1.0000")


def test_config_weights_sum_to_one():
    total = (
        CFG.weight_amount + CFG.weight_date + CFG.weight_reference
        + CFG.weight_counterparty + CFG.weight_description
    )
    assert total == Decimal("1.00")


def test_config_roundtrip_preserves_values():
    data = CFG.to_dict()
    assert data["weight_amount"] == "0.35"
    restored = type(CFG).from_dict(data)
    assert restored == CFG
