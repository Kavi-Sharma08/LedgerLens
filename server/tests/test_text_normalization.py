from app.services.normalization.text import (
    contains_similarity,
    jaccard_similarity,
    normalize_counterparty,
    normalize_reference,
    normalize_text,
    tokenize,
)


def test_normalize_text_spec_example():
    assert normalize_text("  PAYMENT - ABC LTD  ") == "payment abc ltd"


def test_normalize_text_handles_punctuation_and_spaces():
    assert normalize_text("NEFT/PAYMENT---TO,,,ABC   LTD??") == "neft payment to abc ltd"
    assert normalize_text("") is None
    assert normalize_text(None) is None


def test_normalize_reference_equivalences():
    assert normalize_reference("NEFT-1234") == "NEFT1234"
    assert normalize_reference("Ref: NEFT1234") == "NEFT1234"
    assert normalize_reference("reference NEFT 1234") == "NEFT1234"
    assert normalize_reference("inv-2091") == "INV2091"
    assert normalize_reference(None) is None
    assert normalize_reference("   ") is None


def test_counterparty_suffix_stripping():
    assert normalize_counterparty("ABC Pvt Ltd") == "abc"
    assert normalize_counterparty("ABC PRIVATE LIMITED") == "abc"
    assert normalize_counterparty("ABC PVT. LTD.") == "abc"
    assert normalize_counterparty("Beta Industries LLP") == "beta industries"
    assert normalize_counterparty(None) is None


def test_jaccard_is_order_insensitive():
    a = tokenize("payment abc ltd")
    b = tokenize("abc ltd payment")
    assert jaccard_similarity(a, b) == 1.0


def test_jaccard_partial_overlap():
    a = tokenize("payment beta industries inv 7712")
    b = tokenize("beta industries payment part")
    assert 0.0 < jaccard_similarity(a, b) < 1.0


def test_jaccard_empty_sets_are_zero():
    assert jaccard_similarity([], tokenize("abc")) == 0.0


def test_contains_similarity():
    assert contains_similarity(["abc"], ["abc", "industries"])
    assert not contains_similarity(["abc", "xyz"], ["abc"])
