"""Ground truth for the synthetic dataset.

Every scenario pair pins an expected reconciliation outcome so tests assert
BEHAVIOUR, not just execution. Kept next to the dataset so the two cannot
drift apart silently."""

from .dataset import BANK, GATEWAY

# (bankRid, partnerRid(s), expectedStatus, reasonTag)
GROUND_TRUTH: list[dict] = []


def _add(bank_rid, other_rids, expected, reason):
    GROUND_TRUTH.append(
        {
            "bank": bank_rid,
            "others": other_rids if isinstance(other_rids, list) else [other_rids],
            "expectedStatus": expected,
            "reason": reason,
        }
    )


# 1. Exact matches -> MATCHED (EXACT).
for i in range(1, 11):
    _add(f"B-EX-{i:02d}", f"G-EX-{i:02d}", "MATCHED", "exact_identical")

# 2. Fuzzy description / suffix variants -> MATCHED (FUZZY).
for i in range(1, 6):
    _add(f"B-FZ-{i:02d}", f"G-FZ-{i:02d}", "MATCHED", "description_variant")

# 3. Date differences within tolerance -> MATCHED (FUZZY).
for i in range(1, 6):
    _add(f"B-DT-{i:02d}", f"G-DT-{i:02d}", "MATCHED", "date_within_tolerance")

# 4. Missing reference on one side -> confidence reduced to LIKELY_MATCH.
for i in range(1, 5):
    _add(f"B-NR-{i:02d}", f"G-NR-{i:02d}", "LIKELY_MATCH", "reference_missing")

# 5. Missing descriptions both sides; reference + counterparty carry it.
for i in range(1, 5):
    _add(f"B-ND-{i:02d}", f"G-ND-{i:02d}", "MATCHED", "missing_description_ok")

# 6. Ambiguity: twins must NOT be auto-selected.
_add("B-AM-01", ["G-AM-01A", "G-AM-01B"], "AMBIGUOUS", "two_equally_plausible")
_add("B-AM-02", ["G-AM-02A", "G-AM-02B"], "AMBIGUOUS", "two_equally_plausible_no_refs")

# 7. Refund vs original sale: different economic events.
for i in range(1, 4):
    _add(f"B-RF-{i:02d}", f"G-RF-{i:02d}", "UNMATCHED", "refund_not_original_payment")

# 8a. Reversal vs reversal of same event -> MATCHED.
_add("B-RV-01", "G-RV-01", "MATCHED", "reversal_pairs_reversal")
# 8b. Standalone reversals remain unmatched.
_add("B-RV-02", [], "UNMATCHED", "standalone_reversal")

# 9. Fee-band differences -> LIKELY_MATCH + fee exception.
for i in range(1, 4):
    _add(f"B-FE-{i:02d}", f"G-FE-{i:02d}", "LIKELY_MATCH", "possible_processing_fee")

# 10. Settlement split: v1 pairwise cannot aggregate -> UNMATCHED legs.
_add("B-SP-01", ["G-SP-01A", "G-SP-01B"], "UNMATCHED", "one_to_many_future")

# 11a. Pending vs settled -> LIKELY_MATCH with status-conflict evidence.
_add("B-PD-01", "G-PD-01", "LIKELY_MATCH", "pending_vs_settled")
# 11b. Pending-only record.
_add("B-PD-02", [], "UNMATCHED", "pending_without_partner")

# 12. Failed transaction -> EXCEPTION.
_add("B-FL-01", [], "EXCEPTION", "failed_transaction_excluded")

# 13. Zero amount -> EXCEPTION (never auto-matched/duplicated).
_add("B-ZR-01", [], "EXCEPTION", "zero_amount_needs_review")

# 14. Currency mismatch cannot become a monetary match -> EXCEPTION.
for i in range(1, 3):
    _add(f"B-CC-{i:02d}", f"G-CC-{i:02d}", "EXCEPTION", "unsupported_currency_pair")


def expected_for(bank_rid: str) -> dict | None:
    for entry in GROUND_TRUTH:
        if entry["bank"] == bank_rid:
            return entry
    return None
