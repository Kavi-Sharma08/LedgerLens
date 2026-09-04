"""Tests for the AI presentation/formatting layer.

These pin the user-facing guarantees: no MongoDB ObjectIds, no raw JSON or
tool output, human-readable amounts (₹60,000.00), dates ("18 Aug 2026") and
enums ("Needs review") in every AI answer — while `entity_id` / `entity_type`
stay intact for UI navigation.
"""

import re
from datetime import date, datetime

import pytest
from bson import ObjectId

from app.services.ai import ai_service
from app.services.ai.formatting import (
    compile_evidence_answer,
    fmt_amount,
    fmt_date,
    fmt_percent,
    humanize,
    is_object_id,
    scrub_ids,
    scrub_response,
)
from app.services.ai.schemas import AIEvidence, AIFinding, AIResponse

_OBJ_ID = str(ObjectId())
OBJECT_ID_PATTERN = re.compile(r"\b[0-9a-fA-F]{24}\b")


def _no_object_ids(*values):
    for value in values:
        assert not OBJECT_ID_PATTERN.search(value), f"leaked an ObjectId in: {value!r}"


def _assert_clean(response: AIResponse):
    texts = [response.title, response.summary]
    texts += [f.text for f in response.findings] + [d for f in response.findings for d in f.detail]
    texts += [e.label for e in response.evidence]
    texts += [e.value for e in response.evidence]
    texts += [e.source for e in response.evidence]
    texts += list(response.likely_causes) + list(response.recommendations) + list(response.limitations)
    _no_object_ids(*texts)


# ---------------------------------------------------------------------------
# primitive helpers
# ---------------------------------------------------------------------------


def test_is_object_id():
    assert is_object_id(str(ObjectId()))
    assert is_object_id("0000000000000000000000c1")
    assert not is_object_id("INV-TC")
    assert not is_object_id("100.00")
    assert not is_object_id(None)


def test_scrub_ids_removes_object_ids_but_keeps_human_identifiers():
    text = f"Transaction {_OBJ_ID} with reference INV-TC for ₹100.00 on 18 Aug 2026"
    assert scrub_ids(text) == "Transaction with reference INV-TC for ₹100.00 on 18 Aug 2026"
    assert "INV-TC" in scrub_ids(text)


def test_scrub_ids_removes_wrapped_object_id():
    assert scrub_ids(f"ObjectId('{_OBJ_ID}')") == ""


def test_fmt_amount_renders_inr():
    assert fmt_amount("100.00") == "₹100.00"
    assert fmt_amount("60000") == "₹60,000.00"
    assert fmt_amount("60000.00") == "₹60,000.00"
    assert fmt_amount("-1234.5") == "₹-1,234.50"
    assert fmt_amount(None) == ""
    assert fmt_amount("not-a-number") == ""


def test_fmt_percent_renders_percentages():
    assert fmt_percent("0.95") == "95%"
    assert fmt_percent("95.0") == "95%"
    assert fmt_percent("0.5") == "50%"
    assert fmt_percent(None) == ""


def test_fmt_date_renders_human_dates():
    assert fmt_date("2026-08-18") == "18 Aug 2026"
    assert fmt_date("2026-08-18T10:30:00+05:30") == "18 Aug 2026"
    assert fmt_date(date(2026, 8, 18)) == "18 Aug 2026"
    assert fmt_date(datetime(2026, 8, 18, 9, 0)) == "18 Aug 2026"
    assert fmt_date(None) == ""
    assert fmt_date(_OBJ_ID) == ""


def test_humanize_renders_plain_words():
    assert humanize("NEEDS_REVIEW") == "Needs review"
    assert humanize("FAILED_TRANSACTION") == "Failed transaction"
    assert humanize("LIKELY_MATCH") == "Likely match"
    assert humanize("MANUAL_MATCHED") == "Manually matched"
    assert humanize("COMPLETED") == "Completed"
    assert humanize("MATCHED") == "Matched"
    assert humanize("amount_match") == "Amount match"
    assert humanize("date_within_tolerance") == "Date within tolerance"
    assert humanize("OPEN") == "Open"
    assert humanize(_OBJ_ID) == ""


# ---------------------------------------------------------------------------
# scrub_response
# ---------------------------------------------------------------------------


def test_scrub_response_keeps_navigation_ids_but_cleans_visible_text():
    response = AIResponse(
        title=f"Run {_OBJ_ID} analysis",
        summary=f"Transaction {_OBJ_ID} matched.",
        findings=[AIFinding(kind="fact", text=f"Amount matched for record {_OBJ_ID}.", detail=[f"See {_OBJ_ID}"])],
        evidence=[AIEvidence(label=_OBJ_ID, value="₹100.00", source="LedgerLens", entity_type="transaction", entity_id=_OBJ_ID)],
        likely_causes=[f"candidate {_OBJ_ID}"],
        recommendations=[f"recheck {_OBJ_ID}"],
        limitations=[f"ids {_OBJ_ID}"],
        confidence="medium",
    )
    cleaned = scrub_response(response)
    _assert_clean(cleaned)
    # Navigation metadata survives scrubbing untouched.
    assert cleaned.evidence[0].entity_id == _OBJ_ID
    assert cleaned.evidence[0].entity_type == "transaction"
    # A label that was nothing but an id becomes a human entity label.
    assert cleaned.evidence[0].label == "Transaction"
    assert cleaned.evidence[0].value == "₹100.00"
    assert cleaned.findings[0].text == "Amount matched for record ."
    assert "Run analysis" in cleaned.title


def test_scrub_response_drops_empty_lines_and_falls_back_to_safe_title():
    response = AIResponse(title=_OBJ_ID, summary=f"  {_OBJ_ID}  ", evidence=[], confidence="low")
    cleaned = scrub_response(response)
    assert cleaned.title == "Analysis"
    assert cleaned.summary == ""


# ---------------------------------------------------------------------------
# compile_evidence_answer - the autocompiled last-resort answer
# ---------------------------------------------------------------------------


def test_compile_evidence_answer_builds_clean_reconciliation_answer():
    run_id = str(ObjectId())
    match_id = str(ObjectId())
    txn_id = str(ObjectId())
    exc_id = str(ObjectId())

    entries = [
        ("get_reconciliation_summary", {
            "run": {
                "id": run_id,
                "status": "COMPLETED",
                "totalTransactions": 3,
                "matchedCount": 1,
                "likelyMatchCount": 0,
                "ambiguousCount": 0,
                "unmatchedCount": 1,
                "exceptionCount": 1,
                "algorithmVersion": "1.0-test",
                "countsNote": "dev-guidance-that-must-not-leak",
            }
        }),
        ("list_run_matches", {"matches": [{
            "match_id": match_id,
            "transaction_ids": [str(ObjectId()), str(ObjectId())],
            "status": "MATCHED",
            "confidence": "0.95",
            "reasons": ["amount_match", "reference_match"],
        }]}),
        ("list_run_unmatched", {
            "total_unmatched_count": 1,
            "transactions": [{
                "id": txn_id,
                "amount": "60000.00",
                "transaction_date": "2026-08-18",
                "reference": "INV-TC",
                "counterparty": "RHO Wholesale",
            }],
        }),
        ("list_run_exceptions", {"exceptions": [{
            "exception_id": exc_id,
            "reasonCode": "FAILED_TRANSACTION",
            "status": "OPEN",
            "detail": "Counterparty record is in FAILED state.",
        }]}),
    ]

    answer = compile_evidence_answer(entries)

    assert answer["title"] == "Reconciliation outcome: 1 matched, 1 unmatched, 1 exception"
    assert "compared 3 records" in answer["summary"]
    assert "1 match" in answer["summary"]

    all_text = answer["summary"] + " " + " ".join(f["text"] for f in answer["findings"])
    all_text += " " + " ".join(e["label"] + e["value"] + e.get("source", "") for e in answer["evidence"])
    all_text += " " + " ".join(answer["recommendations"] + answer["limitations"]) + " " + answer["title"]
    _no_object_ids(all_text)
    assert "algorithmVersion" not in all_text
    assert "countsNote" not in "".join(e["value"] for e in answer["evidence"])
    assert not any(ch in all_text for ch in ("{", "}"))

    # Navigation metadata preserved per entity.
    entity_ids = {(e["entity_type"], e["entity_id"]) for e in answer["evidence"]}
    assert ("reconciliation", run_id) in entity_ids
    assert ("match", match_id) in entity_ids
    assert ("transaction", txn_id) in entity_ids
    assert ("exception", exc_id) in entity_ids


def test_compile_evidence_answer_dedupes_duplicate_tool_results():
    run_id = str(ObjectId())
    entry = ("get_reconciliation_summary", {
        "run": {"id": run_id, "totalTransactions": 2, "matchedCount": 1, "exceptionCount": 1},
    })
    answer = compile_evidence_answer([entry, entry, entry])
    run_items = [e for e in answer["evidence"] if e["entity_type"] == "reconciliation"]
    assert len(run_items) == 1
    assert answer["title"] == "Reconciliation outcome: 1 matched, 1 exception"


def test_compile_evidence_answer_without_run_is_generic_and_non_raw():
    answer = compile_evidence_answer([
        ("get_exception_notes", {"notes": [], "message": "Notes are restricted."}),
        ("get_match_candidates", {"candidates": []}),
        ("search_workspace_transactions", {"transactions": [], "total_count": 0}),
    ])
    assert answer["title"] == "Analysis summary"
    assert answer["summary"]
    assert answer["findings"]
    for text in [answer["summary"], *[f["text"] for f in answer["findings"]]]:
        _no_object_ids(text)
        assert "{" not in text and "}" not in text
        assert "get_exception_notes" not in text
        assert "search_workspace_transactions" not in text


def test_compile_evidence_answer_renders_unmatched_without_ids_in_value():
    txn_id = str(ObjectId())
    answer = compile_evidence_answer([
        ("list_run_unmatched", {"transactions": [{
            "id": txn_id,
            "amount": "100.00",
            "transaction_date": "2026-08-10",
            "reference": "INV-TC",
            "counterparty": "Acme",
            "source_id": str(ObjectId()),
        }]}),
    ])
    value = answer["evidence"][0]["value"]
    _no_object_ids(value)
    assert "₹100.00" in value
    assert "10 Aug 2026" in value
    assert "INV-TC" in value
    assert "Acme" in value


def test_transaction_evidence_value_uses_financial_identity_not_id():
    """The primary user-facing transaction identity must be
    amount + reference + counterparty + date, never an ObjectId."""
    txn_id = str(ObjectId())
    answer = compile_evidence_answer([
        ("list_run_unmatched", {"transactions": [{
            "id": txn_id,
            "amount": "60000.00",
            "transaction_date": "2026-08-18",
            "reference": "SPRT601",
            "counterparty": "RHO WHOLESALE PRIVATE LIMITED",
            "status": "UNMATCHED",
        }]}),
    ])
    evidence = answer["evidence"][0]
    value = evidence["value"]
    # The visible identity is financial, not the internal ObjectId.
    _no_object_ids(value)
    assert "₹60,000.00" in value
    assert "SPRT601" in value
    assert "RHO WHOLESALE PRIVATE LIMITED" in value
    assert "18 Aug 2026" in value
    assert txn_id not in value
    assert evidence["label"] == "Unmatched transaction"
    # The internal id is preserved for the "View transaction" action only.
    assert evidence["entity_id"] == txn_id
    assert evidence["entity_type"] == "transaction"


def test_evidence_value_preserves_long_counterparty_and_description():
    """Long counterparty / description text must be preserved verbatim and
    contain no ObjectIds so the frontend can wrap it inside the chat card."""
    long_counterparty = "RHO WHOLESALE PRIVATE LIMITED AND SONS ENTERPRISES"
    description = "PAYMENT AGAINST INVOICE NO SPRT601 DATED 12 AUGUST 2026 ISSUED BY SUPPLIER"
    answer = compile_evidence_answer([
        ("list_run_unmatched", {"transactions": [{
            "id": str(ObjectId()),
            "amount": "2049.24",
            "transaction_date": "2026-08-05",
            "reference": "NEFT1004",
            "counterparty": long_counterparty,
            "description": description,
        }]}),
    ])
    value = answer["evidence"][0]["value"]
    _no_object_ids(value)
    assert long_counterparty in value
    assert "₹2,049.24" in value
    assert "5 Aug 2026" in value
    assert "NEFT1004" in value


# ---------------------------------------------------------------------------
# ai_service._evidence_to_response - reconciliation autocompiled fallback
# ---------------------------------------------------------------------------


def test_evidence_to_response_autocompiles_without_leaking_run_id():
    run_id = str(ObjectId())
    evidence = {
        "run": {
            "run": {
                "id": run_id,
                "status": "COMPLETED",
                "totalTransactions": 3,
                "matchedCount": 1,
                "unmatchedCount": 1,
                "exceptionCount": 1,
            }
        },
        "matches": [{
            "match_id": str(ObjectId()),
            "confidence": "0.95",
            "reasons": ["amount_match", "reference_match"],
        }],
        "unmatched": [{
            "id": str(ObjectId()),
            "amount": "60000.00",
            "currency": "INR",
            "reference": "INV-TC",
            "counterparty": "RHO Wholesale",
            "transaction_date": "2026-08-18",
            "status": "UNMATCHED",
        }],
        "exceptions": [{
            "exception_id": str(ObjectId()),
            "reasonCode": "FAILED_TRANSACTION",
            "status": "OPEN",
            "detail": "Counterparty record is in FAILED state.",
        }],
    }

    response = ai_service._evidence_to_response(evidence)

    assert response.title == "Reconciliation outcome: 1 matched, 1 unmatched, 1 exception"
    _assert_clean(response)
    # Autocompiled summary is real counts, not a raw run-id dump.
    assert run_id not in response.title and run_id not in response.summary
    assert "compared 3 records" in response.summary
    # Evidence remains navigable while being human-readable.
    assert any(e.entity_type == "reconciliation" and e.entity_id == run_id for e in response.evidence)
    assert any(e.value and "₹60,000.00" in e.value for e in response.evidence)