"""Deterministic synthetic financial dataset.

No randomness anywhere: every record is an explicit scenario so tests are
stable forever. The dataset intentionally covers every edge case from the
phase spec and ships WITH ground truth (see ground_truth.py) so reconciliation
behaviour is verified, not just exercised.

Sources:
    B = BANK            (HDFC current account)
    G = PAYMENT_PROCESSOR (Razorpay-like gateway)
    A = ACCOUNTING      (Tally-like ledger export)

Identifiers: stable sourceRecordIds like "B-EX-01", "G-EX-01", used by ground
truth to pin expected outcomes.
"""

from dataclasses import dataclass

BANK = "B"
GATEWAY = "G"
ACCOUNTING = "A"


@dataclass(frozen=True)
class RecordSpec:
    """One raw financial record, pre-normalization."""

    source: str
    rid: str                      # sourceRecordId (may be empty -> missing case)
    date: str                     # ISO date
    amount: str                   # decimal string, signed or unsigned
    description: str = ""
    reference: str = ""
    counterparty: str = ""
    currency: str = "INR"
    type: str = ""                # SALE/PAYMENT/REFUND/REVERSAL/FEE/...
    status: str = "SETTLED"


def _series(prefix: str, count: int, start_amount: str, day: str, party: str) -> list[RecordSpec]:
    """Deterministic baseline series with distinct amounts/parties."""
    from decimal import Decimal

    base = Decimal(start_amount)
    out = []
    for i in range(count):
        amount = (base + Decimal("137.31") * i).quantize(Decimal("0.01"))
        out.append(
            RecordSpec(
                source=prefix[0],
                rid=f"{prefix}-{i + 1:02d}",
                date=day,
                amount=f"{amount:.2f}",
                description=f"PAYMENT {party} {i + 1} PVT LTD",
                reference=f"NEFT{1000 + i}",
                counterparty=f"{party} {i + 1} PVT LTD",
            )
        )
    return out


def bank_records() -> list[RecordSpec]:
    records: list[RecordSpec] = []

    # 1. Exact matches (10): identical economics across bank/gateway.
    for i, r in enumerate(_series("B-EX", 10, "1500.00", "2026-08-05", "OMKAR")):
        records.append(r)

    # 2. Fuzzy description matches (5): partial token overlap, same refs.
    fuzzy_desc_bank = [
        "PAYMENT BETA INDUSTRIES INV 7712",
        "NEFT CREDIT GAMUT SOLUTIONS",
        "SETTLEMENT DELTA RETAIL UTR",
        "INWARD REMIT EPSILON FOODS",
        "PAYMENT ZETA LOGISTICS CHALLAN 55",
    ]
    for i in range(5):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-FZ-{i + 1:02d}",
                date="2026-08-06",
                amount=f"{2100.50 + i * 311.11:.2f}",
                description=fuzzy_desc_bank[i],
                reference=f"UTR{5000 + i}",
                counterparty=["BETA INDUSTRIES PVT LTD", "GAMUT SOLUTIONS LTD",
                              "DELTA RETAIL PVT LTD", "EPSILON FOODS LLP",
                              "ZETA LOGISTICS PVT LTD"][i],
            )
        )

    # 3. Date differences (5): -1/-1/+2/+3/+1 days vs partner.
    date_offsets = ["2026-08-09", "2026-08-09", "2026-08-08", "2026-08-07", "2026-08-10"]
    for i in range(5):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-DT-{i + 1:02d}",
                date=date_offsets[i],
                amount=f"{3300.00 + i * 211.45:.2f}",
                description=f"PAYMENT THETA TRADERS {i + 1}",
                reference=f"NEFT7{i}{i}00",
                counterparty="THETA TRADERS PVT LTD",
            )
        )

    # 4. Missing references on partner side (4).
    for i in range(4):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-NR-{i + 1:02d}",
                date="2026-08-12",
                amount=f"{4400.75 + i * 97.77:.2f}",
                description=f"PAYMENT IOTA STORES {i + 1}",
                reference=f"REFNR{i}009",
                counterparty="IOTA STORES PVT LTD",
            )
        )

    # 5. Missing descriptions both sides (4) — reference carries identity.
    for i in range(4):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-ND-{i + 1:02d}",
                date="2026-08-13",
                amount=f"{5200.25 + i * 71.71:.2f}",
                reference=f"CHOLAND{i}88",
                counterparty="KAPPA MART PVT LTD",
            )
        )

    # 6. Ambiguity seeds (2 groups): one bank record, two twin gateway records.
    for i in range(2):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-AM-{i + 1:02d}",
                date="2026-08-14",
                amount="6500.00" if i == 0 else "7200.00",
                description="PAYMENT LAMBDA CORP",
                reference="" if i == 0 else f"PAYX{i}",
                counterparty="LAMBDA CORP PVT LTD",
            )
        )

    # 7. Refund conflicts (3): bank REFUND must not match original gateway SALE.
    for i in range(3):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-RF-{i + 1:02d}",
                date="2026-08-15",
                amount=f"{1800.00 + i * 404.40:.2f}",
                description=f"REFUND MU NU {i + 1}",
                reference=f"RFND{200 + i}",
                counterparty="MU NU RETAIL PVT LTD",
                type="REFUND",
            )
        )

    # 8. Reversals (2): one pairs a like REVERSAL, one stands alone.
    records.append(
        RecordSpec(
            source=BANK, rid="B-RV-01", date="2026-08-16",
            amount="2750.00", description="REVERSAL XI PAY",
            reference="RVSL301", counterparty="XI PAYMENTS PVT LTD", type="REVERSAL",
        )
    )
    records.append(
        RecordSpec(
            source=BANK, rid="B-RV-02", date="2026-08-16",
            amount="3999.00", description="REVERSAL OMICRON",
            reference="RVSL302", counterparty="OMICRON LABS PVT LTD", type="REVERSAL",
        )
    )

    # 9. Fee-band differences (3): gateway gross vs net bank credit.
    fee_pairs = [("10000.00", "9900.00"), ("8000.00", "7840.00"), ("15000.00", "14700.00")]
    for i, (gross, net) in enumerate(fee_pairs):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-FE-{i + 1:02d}",
                date="2026-08-17",
                amount=net,
                description=f"SETTLEMENT PI COMMERCE {i + 1}",
                reference=f"PAYOUT{400 + i}",
                counterparty="PI COMMERCE PVT LTD",
            )
        )

    # 10. Settlement split seed (1): bank 100000 vs gateway 60000 + 40000.
    records.append(
        RecordSpec(
            source=BANK, rid="B-SP-01", date="2026-08-18",
            amount="100000.00", description="SETTLEMENT RHO WHOLESALE",
            reference="PAYOUT999", counterparty="RHO WHOLESALE PVT LTD",
        )
    )

    # 11. Pending pair (1) + pending-only (1).
    records.append(
        RecordSpec(
            source=BANK, rid="B-PD-01", date="2026-08-19",
            amount="5600.00", description="PAYMENT SIGMA SOFT",
            reference="NEFT8121", counterparty="SIGMA SOFT PVT LTD", status="SETTLED",
        )
    )
    records.append(
        RecordSpec(
            source=BANK, rid="B-PD-02", date="2026-08-19",
            amount="6100.00", description="PAYMENT TAU SYSTEMS",
            reference="NEFT8131", counterparty="TAU SYSTEMS PVT LTD", status="PENDING",
        )
    )

    # 12. Failed transaction (1) -> EXCEPTION.
    records.append(
        RecordSpec(
            source=BANK, rid="B-FL-01", date="2026-08-20",
            amount="4500.00", description="PAYMENT UPSILON ENTERPRISES",
            reference="NEFT8141", counterparty="UPSILON ENTERPRISES PVT LTD",
            status="FAILED",
        )
    )

    # 13. Zero amount (1) -> EXCEPTION.
    records.append(
        RecordSpec(
            source=BANK, rid="B-ZR-01", date="2026-08-20",
            amount="0.00", description="ADJUSTMENT ENTRY ZERO",
            reference="ZERO001", counterparty="INTERNAL",
        )
    )

    # 14. Currency-mismatch mirrors (2): INR here, USD twins on gateway.
    for i in range(2):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-CC-{i + 1:02d}",
                date="2026-08-21",
                amount=f"{12000.00 + i * 2500.00:.2f}",
                description=f"PAYMENT PHI GLOBALS {i + 1}",
                reference=f"SWIFT{600 + i}",
                counterparty="PHI GLOBALS PVT LTD",
                currency="INR",
            )
        )

    # 15. Bank-only unmatched (6): unique parties/dates/amounts.
    unmatched_days = ["2026-08-22", "2026-08-22", "2026-08-23", "2026-08-23", "2026-08-24", "2026-08-24"]
    for i in range(6):
        records.append(
            RecordSpec(
                source=BANK,
                rid=f"B-UM-{i + 1:02d}",
                date=unmatched_days[i],
                amount=f"{7000.00 + i * 333.33:.2f}",
                description=f"PAYMENT UNMATCHED VENDOR {i + 1} LTD",
                reference=f"UNIQ70{i}",
                counterparty=f"ORPHAN VENDOR {i + 1} PVT LTD",
            )
        )

    return records


def gateway_records() -> list[RecordSpec]:
    records: list[RecordSpec] = []

    # Exact-match partners.
    for i, r in enumerate(_series("G-EX", 10, "1500.00", "2026-08-05", "OMKAR")):
        records.append(r)

    # Fuzzy partners: word-order/partial descriptions.
    fuzzy_desc_gw = [
        "BETA INDUSTRIES PAYMENT PART",
        "CREDIT GAMUT SOLN NEFT",
        "DELTA RETAIL SETTLEMENT",
        "EPSILON FOODS RECEIVABLE",
        "ZETA LOGISTICS PAYMENT",
    ]
    for i in range(5):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-FZ-{i + 1:02d}",
                date="2026-08-06",
                amount=f"{2100.50 + i * 311.11:.2f}",
                description=fuzzy_desc_gw[i],
                reference=f"UTR{5000 + i}",
                counterparty=["BETA INDUSTRIES PRIVATE LIMITED", "GAMUT SOLUTIONS LIMITED",
                              "DELTA RETAIL PRIVATE LIMITED", "EPSILON FOODS LLP",
                              "ZETA LOGISTICS PRIVATE LIMITED"][i],
            )
        )

    # Date-difference partners (+1/+1/-2/+3/-1 relative to bank rows above).
    date_offsets = ["2026-08-10", "2026-08-10", "2026-08-10", "2026-08-10", "2026-08-09"]
    for i in range(5):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-DT-{i + 1:02d}",
                date=date_offsets[i],
                amount=f"{3300.00 + i * 211.45:.2f}",
                description=f"THETA TRADERS {i + 1} PAYMENT",
                reference=f"NEFT7{i}{i}00",
                counterparty="THETA TRADERS PRIVATE LIMITED",
            )
        )

    # Missing-reference partners (no Reference column value at all).
    for i in range(4):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-NR-{i + 1:02d}",
                date="2026-08-12",
                amount=f"{4400.75 + i * 97.77:.2f}",
                description=f"IOTA STORES {i + 1} PAYMENT",
                counterparty="IOTA STORES PRIVATE LIMITED",
            )
        )

    # Missing-description partners.
    for i in range(4):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-ND-{i + 1:02d}",
                date="2026-08-13",
                amount=f"{5200.25 + i * 71.71:.2f}",
                reference=f"CHOLAND{i}88",
                counterparty="KAPPA MART PRIVATE LIMITED",
            )
        )

    # Ambiguous twins: two equally plausible partners per bank row.
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-AM-01A", date="2026-08-14",
            amount="6500.00", description="LAMBDA CORP PAYMENT",
            reference="PAY1", counterparty="LAMBDA CORP PRIVATE LIMITED",
        )
    )
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-AM-01B", date="2026-08-14",
            amount="6500.00", description="LAMBDA CORP PAYMENT",
            reference="PAY2", counterparty="LAMBDA CORP PRIVATE LIMITED",
        )
    )
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-AM-02A", date="2026-08-14",
            amount="7200.00", description="LAMBDA CORP PAYMENT",
            counterparty="LAMBDA CORP PRIVATE LIMITED",
        )
    )
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-AM-02B", date="2026-08-14",
            amount="7200.00", description="LAMBDA CORP PAYMENT",
            counterparty="LAMBDA CORP PRIVATE LIMITED",
        )
    )

    # Refund originals (gateway side recorded them as SALE).
    for i in range(3):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-RF-{i + 1:02d}",
                date="2026-08-15",
                amount=f"{1800.00 + i * 404.40:.2f}",
                description=f"MU NU ORDER {i + 1} CAPTURE",
                reference=f"RFND{200 + i}",
                counterparty="MU NU RETAIL LIMITED",
                type="SALE",
            )
        )

    # Reversal partner for B-RV-01 (same event, both REVERSAL).
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-RV-01", date="2026-08-16",
            amount="2750.00", description="XI PAY REVERSAL PROCESSED",
            reference="RVSL301", counterparty="XI PAYMENTS LIMITED", type="REVERSAL",
        )
    )
    # Standalone reversal (no bank counterpart yet).
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-RV-03", date="2026-08-17",
            amount="1234.00", description="OMICRON REVERSAL PENDING BANK",
            reference="RVSL303", counterparty="OMICRON LABS LIMITED", type="REVERSAL",
        )
    )

    # Fee-band gross sides.
    fee_gross = ["10000.00", "8000.00", "15000.00"]
    for i, gross in enumerate(fee_gross):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-FE-{i + 1:02d}",
                date="2026-08-17",
                amount=gross,
                description=f"PI COMMERCE {i + 1} CAPTURE BATCH",
                reference=f"PAYOUT{400 + i}",
                counterparty="PI COMMERCE LIMITED",
            )
        )
    # Explicit FEE record (its own economic event).
    records.append(
        RecordSpec(
            source=GATEWAY, rid="G-FE-90", date="2026-08-17",
            amount="200.00", description="GATEWAY PROCESSING FEE AUG W2",
            reference="FEEAUGW2", counterparty="PI COMMERCE LIMITED", type="FEE",
        )
    )

    # Settlement-split legs.
    records.append(
        RecordSpec(source=GATEWAY, rid="G-SP-01A", date="2026-08-18",
                   amount="60000.00", description="RHO WHOLESALE SPLIT 1",
                   reference="SPRT601", counterparty="RHO WHOLESALE PRIVATE LIMITED")
    )
    records.append(
        RecordSpec(source=GATEWAY, rid="G-SP-01B", date="2026-08-18",
                   amount="40000.00", description="RHO WHOLESALE SPLIT 2",
                   reference="SPRT602", counterparty="RHO WHOLESALE PRIVATE LIMITED")
    )

    # Pending partner + pending-only.
    records.append(
        RecordSpec(source=GATEWAY, rid="G-PD-01", date="2026-08-19",
                   amount="5600.00", description="SIGMA SOFT PAYMENT",
                   reference="NEFT8121", counterparty="SIGMA SOFT LIMITED",
                   status="PENDING")
    )
    records.append(
        RecordSpec(source=GATEWAY, rid="G-PD-02", date="2026-08-20",
                   amount="6150.00", description="UPSILON PENDING CAPTURE",
                   reference="NEFT8151", counterparty="UPSILON ENTERPRISES LIMITED",
                   status="PENDING")
    )

    # Failed transaction.
    records.append(
        RecordSpec(source=GATEWAY, rid="G-FL-01", date="2026-08-20",
                   amount="900.00", description="CHI STORES FAILED AUTH",
                   reference="AUTH771", counterparty="CHI STORES LIMITED",
                   status="FAILED")
    )

    # Zero amount.
    records.append(
        RecordSpec(source=GATEWAY, rid="G-ZR-01", date="2026-08-21",
                   amount="0.00", description="VALIDATION TEST RECORD",
                   reference="TESTZERO", counterparty="INTERNAL")
    )

    # USD mirrors of the INR bank rows (unsupported cross-currency).
    for i in range(2):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-CC-{i + 1:02d}",
                date="2026-08-21",
                amount=f"{12000.00 + i * 2500.00:.2f}",
                description=f"PHI GLOBALS {i + 1} INTERNATIONAL",
                reference=f"SWIFT{600 + i}",
                counterparty="PHI GLOBALS LIMITED",
                currency="USD",
            )
        )

    # Gateway-only unmatched (6).
    gw_unmatched_days = ["2026-08-22", "2026-08-22", "2026-08-23", "2026-08-23", "2026-08-24", "2026-08-24"]
    for i in range(6):
        records.append(
            RecordSpec(
                source=GATEWAY,
                rid=f"G-UM-{i + 1:02d}",
                date=gw_unmatched_days[i],
                amount=f"{7500.00 + i * 222.22:.2f}",
                description=f"LONE CUSTOMER {i + 1} CHECKOUT",
                reference=f"GWONLY8{i}",
                counterparty=f"LONE CUSTOMER {i + 1} LIMITED",
            )
        )

    return records


def accounting_records() -> list[RecordSpec]:
    """Accounting export: mirrors part of the exact/fuzzy population plus its
    own unmatched tail — adds volume and a third perspective."""
    records: list[RecordSpec] = []

    # Mirror of first 6 exact amounts (ledger view of the same events).
    mirrored = _series("A-EX", 6, "1500.00", "2026-08-05", "OMKAR")
    for r in mirrored:
        records.append(r)

    # Ledger-only entries (dr/cr style descriptions, no bank counterpart).
    for i in range(34):
        records.append(
            RecordSpec(
                source=ACCOUNTING,
                rid=f"A-LD-{i + 1:02d}",
                date=f"2026-08-{(i % 28) + 1:02d}",
                amount=f"{250.00 + i * 61.60:.2f}",
                description=f"JOURNAL ENTRY PSIPHI LEDGER {i + 1}",
                reference=f"JV{9000 + i}",
                counterparty="PSIPHI BOOKS PVT LTD",
            )
        )
    return records


def all_records() -> list[RecordSpec]:
    return bank_records() + gateway_records() + accounting_records()


def records_for_source(source_key: str) -> list[RecordSpec]:
    return [r for r in all_records() if r.source == source_key]


SOURCE_NAMES = {
    BANK: ("HDFC Current Account", "BANK"),
    GATEWAY: ("Razorpay Settlements", "PAYMENT_PROCESSOR"),
    ACCOUNTING: ("Tally Export", "ACCOUNTING"),
}
