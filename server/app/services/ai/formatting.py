"""Shared presentation helpers for every AI answer.

This is the ONLY layer that converts raw backend values (MongoDB ObjectIds,
JSON tool output, internal enum keys, ISO timestamps) into clean, human-readable
financial text for the reconciliation surfaces. It never touches
`entity_id` / `entity_type`, which stay internal for UI navigation.

Rules enforced here:
  - 24-hex MongoDB ObjectIds never appear in user-facing text.
  - amounts render in INR (e.g. "₹60,000.00"), dates as "18 Aug 2026",
    enum/code values as plain words ("Needs review", "Completed", "Matched").
  - raw JSON, field names and tool output are never emitted to the user.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, DecimalException

from .schemas import AIEvidence, AIFinding, AIResponse

_OBJECT_ID_RE = re.compile(r"\b[0-9a-fA-F]{24}\b")
_OBJECT_ID_WRAP_RE = re.compile(
    r"ObjectId\(\s*(['\"])[0-9a-fA-F]{24}\1\s*\)", re.IGNORECASE
)
_WS_RE = re.compile(r"\s{2,}")

_MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Enum/code values that read better as an explicit phrase than the generic
# title-casing rule ("Needs review", "Under investigation", ...).
_HUMAN_OVERRIDES = {
    "NEEDS_REVIEW": "Needs review",
    "CANDIDATE_COLLISION": "Candidate collision",
    "FAILED_TRANSACTION": "Failed transaction",
    "POSSIBLE_FEE": "Possible fee",
    "STATUS_CONFLICT": "Status conflict",
    "UNSUPPORTED_CURRENCY": "Unsupported currency",
    "ZERO_AMOUNT": "Zero amount",
    "LIKELY_MATCH": "Likely match",
    "MANUAL_MATCHED": "Manually matched",
    "ONE_TO_MANY": "One to many",
    "MANY_TO_ONE": "Many to one",
    "INVESTIGATING": "Under investigation",
}


def is_object_id(value) -> bool:
    """True when `value` is a bare 24-hex MongoDB ObjectId string."""
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{24}", value))


def scrub_ids(text) -> str:
    """Remove every ObjectId the text may contain, collapsing leftover space.

    Never removes anything else — human identifiers such as references,
    counterparties and invoice numbers are preserved verbatim.
    """
    if text is None:
        return ""
    out = _OBJECT_ID_WRAP_RE.sub("", str(text))
    out = _OBJECT_ID_RE.sub("", out)
    out = _WS_RE.sub(" ", out)
    return out.strip()


def humanize(value) -> str:
    """Render an internal enum/code value as plain words.

    "NEEDS_REVIEW" -> "Needs review", "amount_match" -> "Amount match",
    "COMPLETED" -> "Completed". Returns "" for values that are (or hide) an
    ObjectId so a bare id can never surface as a human label.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if _OBJECT_ID_RE.search(s):
        return ""
    normalized = s.replace("-", "_")
    override = _HUMAN_OVERRIDES.get(normalized.upper())
    if override:
        return override
    words = [w for w in normalized.split("_") if w]
    if not words:
        return ""
    return " ".join([words[0].capitalize(), *[w.lower() for w in words[1:]]]).strip()


def fmt_amount(value) -> str:
    """Render an amount in INR with grouping and 2 decimals: "₹60,000.00"."""
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(str(value).replace(",", "").lstrip("₹").strip())
    except (DecimalException, ValueError):
        return ""
    if amount.is_nan():
        return ""
    negative = amount < 0
    magnitude = abs(amount).quantize(Decimal("0.01"))
    body = f"{magnitude:,.2f}"
    if negative:
        body = f"-{body}"
    return f"₹{body}"


def fmt_percent(value) -> str:
    """Render a confidence/score as a human percentage.

    Accepts either a 0-1 fraction ("0.95" -> "95%") or an already-percent
    number ("95.0" -> "95%"). Returns "" when the value can't be parsed.
    """
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(str(value).replace("%", "").strip())
    except (DecimalException, ValueError):
        return ""
    if amount.is_nan():
        return ""
    if amount > 1:
        return f"{amount.quantize(Decimal('1')):.0f}%"
    return f"{(amount * 100).quantize(Decimal('1')):.0f}%"


def fmt_date(value) -> str:
    """Render a date/datetime or ISO string as "18 Aug 2026"."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        day = value.date()
    elif isinstance(value, date):
        day = value
    else:
        s = str(value).strip()
        if not s or _OBJECT_ID_RE.search(s):
            return ""
        # Take the calendar-date portion before any time component.
        s = s.split("T")[0]
        parsed = None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        if parsed is None:
            return ""
        day = parsed
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _plural(value, word: str) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return f"{value} {word}"
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def scrub_response(response: AIResponse) -> AIResponse:
    """Return an AIResponse with every user-visible string scrubbed of
    ObjectIds, while preserving the structured contract and the internal
    `entity_id` / `entity_type` hints used for UI navigation."""
    title = scrub_ids(response.title).strip()
    if not title:
        title = "Analysis"
    summary = scrub_ids(response.summary).strip()

    findings: list[AIFinding] = []
    for finding in response.findings:
        text = scrub_ids(finding.text).strip()
        detail = [d for d in (scrub_ids(x).strip() for x in finding.detail) if d]
        if not text and not detail:
            continue
        if not text and detail:
            text, detail = detail[0], detail[1:]
        findings.append(AIFinding(kind=finding.kind, text=text, detail=detail))

    evidence: list[AIEvidence] = []
    for item in response.evidence:
        label = "" if is_object_id(item.label) else scrub_ids(item.label).strip()
        value = scrub_ids(item.value).strip()
        if not label and not value:
            continue
        evidence.append(
            AIEvidence(
                label=label or humanize(item.entity_type) or "Record",
                value=value,
                source=scrub_ids(item.source).strip(),
                entity_type=item.entity_type,
                entity_id=item.entity_id,
            )
        )

    return AIResponse(
        title=title,
        summary=summary,
        findings=findings,
        evidence=evidence,
        likely_causes=[s for s in (scrub_ids(c).strip() for c in response.likely_causes) if s],
        recommendations=[s for s in (scrub_ids(r).strip() for r in response.recommendations) if s],
        confidence=response.confidence,
        limitations=[s for s in (scrub_ids(l).strip() for l in response.limitations) if s],
    )


# ---------------------------------------------------------------------------
# Auto-compiled evidence answer (last-resort fallback when the LLM produced no
# text). Turns the raw tool JSON already in the conversation into a clean,
# human-readable structured answer — never a raw dump.
# ---------------------------------------------------------------------------

_RUN_COUNT_KEYS = (
    ("totalTransactions", "total"),
    ("matchedCount", "matched"),
    ("likelyMatchCount", "likely"),
    ("ambiguousCount", "ambiguous"),
    ("unmatchedCount", "unmatched"),
    ("exceptionCount", "exceptions"),
)


def _absorb_counts(counts: dict, run: dict) -> None:
    for src, dst in _RUN_COUNT_KEYS:
        value = run.get(src)
        if value is not None:
            counts[dst] = value


def _transaction_evidence_value(txn: dict) -> str:
    parts = []
    amount = fmt_amount(txn.get("amount"))
    if amount:
        parts.append(amount)
    day = fmt_date(txn.get("transaction_date"))
    if day:
        parts.append(day)
    reference = scrub_ids(str(txn.get("reference") or "")).strip()
    if reference:
        parts.append(reference)
    counterparty = scrub_ids(str(txn.get("counterparty") or "")).strip()
    if counterparty:
        parts.append(counterparty)
    return " · ".join(parts)


def _exception_evidence_value(exc: dict) -> str:
    parts = [p for p in (
        humanize(exc.get("reasonCode")),
        humanize(exc.get("status")),
        scrub_ids(str(exc.get("detail") or "")).strip(),
    ) if p]
    return " · ".join(parts)


def _match_evidence_value(match: dict) -> str:
    reasons = [r for r in (humanize(x) for x in (match.get("reasons") or [])) if r][:3]
    confidence = fmt_percent(match.get("confidence"))
    parts = [", ".join(reasons)] if reasons else []
    if confidence:
        parts.append(f"{confidence} confidence")
    return " · ".join(parts)


def _append_evidence(evidence: list[dict], seen: set, entity_type: str, entity_id, label: str, value: str) -> None:
    if entity_id:
        key = (entity_type, str(entity_id))
        if key in seen:
            return
        seen.add(key)
    evidence.append({
        "label": label,
        "value": value,
        "source": "LedgerLens",
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else "",
    })


def compile_evidence_answer(entries: list[tuple[str, dict | None]]) -> dict:
    """Compile a clean structured answer dict from tool evidence.

    `entries` is an ordered list of (tool_name, parsed_tool_data) pairs. Every
    value presented to the user is derived from known fields and formatted
    human-readably; unknown shapes are dropped rather than dumped. `entity_id`
    values are preserved on evidence items purely for UI navigation.
    """
    counts: dict = {}
    run_ids: list[str] = []
    matches: list[dict] = []
    unmatched: list[dict] = []
    exceptions: list[dict] = []
    transactions: list[dict] = []

    for tool_name, data in entries:
        if not isinstance(data, dict):
            continue
        name = tool_name or ""
        if name in ("get_reconciliation_summary", "get_reconciliation_run"):
            run = data.get("run")
            if isinstance(run, dict):
                _absorb_counts(counts, run)
                run_id = run.get("id")
                if run_id and run_id not in run_ids:
                    run_ids.append(run_id)
        elif name == "list_reconciliation_runs":
            for run in (data.get("runs") or []):
                if isinstance(run, dict):
                    _absorb_counts(counts, run)
        elif name == "list_run_unmatched":
            total = data.get("total_unmatched_count")
            if total is not None:
                counts["unmatched"] = total
            unmatched.extend(
                t for t in (data.get("transactions") or []) if isinstance(t, dict)
            )
        elif name == "list_run_matches":
            matches.extend(m for m in (data.get("matches") or []) if isinstance(m, dict))
        elif name == "list_run_exceptions":
            exceptions.extend(
                e for e in (data.get("exceptions") or []) if isinstance(e, dict)
            )
        elif name == "get_transaction":
            txn = data.get("transaction")
            if isinstance(txn, dict) and (txn.get("id") or txn.get("amount")):
                transactions.append(txn)
        elif name == "get_match":
            match = data.get("match")
            if isinstance(match, dict) and match.get("id"):
                matches.append(match)
        elif name == "get_exception":
            exc = data.get("exception")
            if isinstance(exc, dict) and exc.get("id"):
                exceptions.append(exc)

    statement = _counts_statement(counts)
    findings: list[dict] = []
    evidence: list[dict] = []
    seen: set = set()

    for key, label in (
        ("total", "Total transactions"),
        ("matched", "Matched"),
        ("likely", "Likely matches"),
        ("ambiguous", "Ambiguous"),
        ("unmatched", "Unmatched"),
        ("exceptions", "Exceptions"),
    ):
        if counts.get(key) is not None:
            findings.append({"kind": "fact", "text": f"{label}: {counts[key]}.", "detail": []})

    if run_ids:
        value_parts = []
        for key, word in (("matched", "matched"), ("unmatched", "unmatched"), ("exceptions", "exception")):
            if counts.get(key) is not None:
                value_parts.append(_plural(counts[key], word))
        run_value = " · ".join(value_parts) if value_parts else f"{len(run_ids)} run(s)"
        _append_evidence(
            evidence, seen, "reconciliation", run_ids[0],
            "Reconciliation run", run_value,
        )

    for match in matches[:5]:
        match_value = _match_evidence_value(match)
        if not match_value:
            continue
        _append_evidence(
            evidence, seen, "match", match.get("id") or match.get("match_id"),
            "Matched record", match_value,
        )
    if matches:
        findings.append({
            "kind": "fact",
            "text": f"{len(matches)} match record(s) retrieved as sample evidence.",
            "detail": [],
        })

    for txn in unmatched[:5]:
        txn_value = _transaction_evidence_value(txn)
        if not txn_value:
            continue
        _append_evidence(
            evidence, seen, "transaction", txn.get("id"),
            "Unmatched transaction", txn_value,
        )
    if unmatched:
        findings.append({
            "kind": "fact",
            "text": f"{len(unmatched)} unmatched record(s) retrieved as sample evidence.",
            "detail": [],
        })

    for exc in exceptions[:5]:
        exc_value = _exception_evidence_value(exc)
        if not exc_value:
            continue
        _append_evidence(
            evidence, seen, "exception", exc.get("exception_id") or exc.get("id"),
            "Exception", exc_value,
        )
    if exceptions:
        findings.append({
            "kind": "fact",
            "text": f"{len(exceptions)} exception record(s) retrieved as sample evidence.",
            "detail": [],
        })

    if not counts and not statement and not findings:
        statement = "LedgerLens reviewed its reconciliation records related to this question."
    if not findings:
        findings.append({
            "kind": "fact",
            "text": "The reconciliation outcome is summarised from the records retrieved for this question.",
            "detail": [],
        })

    title = _title_from_counts(counts)
    recommendations = []
    if counts.get("unmatched"):
        recommendations.append(
            f"Review the {_plural(counts['unmatched'], 'unmatched record')} with no match decision."
        )
    if counts.get("exceptions"):
        recommendations.append(
            f"Review the {_plural(counts['exceptions'], 'exception')} flagged during the run."
        )

    return {
        "title": title,
        "summary": statement,
        "findings": findings,
        "evidence": evidence,
        "likely_causes": [],
        "recommendations": recommendations,
        "confidence": "medium",
        "limitations": [
            "The full narrative could not be generated; this summary was compiled "
            "directly from the reconciliation records that were retrieved.",
        ],
    }


def _title_from_counts(counts: dict) -> str:
    if counts:
        parts = []
        for key, word in (("matched", "matched"), ("unmatched", "unmatched"), ("exceptions", "exception")):
            if counts.get(key) is not None:
                parts.append(_plural(counts[key], word))
        if parts:
            return "Reconciliation outcome: " + ", ".join(parts)
    return "Analysis summary"


def _counts_statement(counts: dict) -> str:
    if not counts:
        return ""
    total = counts.get("total")
    matched = counts.get("matched")
    unmatched = counts.get("unmatched")
    exceptions = counts.get("exceptions")
    if total is None and matched is None and unmatched is None and exceptions is None:
        return ""
    head = f"This run compared {total} records." if total is not None else "This run's outcome:"
    pieces = []
    if matched is not None:
        pieces.append(f"{_plural(matched, 'match')}")
    if unmatched is not None:
        pieces.append(f"{_plural(unmatched, 'unmatched record')}")
    if exceptions is not None:
        pieces.append(f"{_plural(exceptions, 'exception')}")
    if pieces:
        head += f" {', '.join(pieces)}."
    return head