# LedgerLens Reconciliation Engine (Phase 2)

Status: **implemented** — this document describes the engine exactly as it
exists in `server/app/services/matching/` and `server/app/services/reconciliation_service.py`.
It is not aspirational; every threshold, rule and behaviour below is verifiable
in code and pinned by tests (`server/tests/`).

## 1. Purpose

LedgerLens determines which transactions from different financial sources
(bank, payment gateway, accounting export, card processor, ERP) most likely
represent the same real-world financial event.

The deterministic engine answers one question, explainably:

> "How similar are these two financial records?"

It deliberately does NOT answer:

> "Why might these records differ?"

That second question belongs to a future AI investigation agent (section 26).
The deterministic layer must remain auditable: every decision stores its score,
the component breakdown behind the score, human-readable reasons, and the exact
configuration that produced it.

## 2. Reconciliation pipeline

```
Source files (CSV / JSONL upload)
    |
    v
Extraction            app/services/ingestion/extraction.py
    |                 header aliasing -> resolved rows, unknown columns kept as metadata
    v
Normalization         app/services/normalization/* + ingestion/pipeline.py
    |                 money (Decimal), dates (UTC-midnight calendar days),
    |                 text/reference/counterparty normalization, direction split
    v
Validation            per-row; failures become RowErrors, never crashes
    |
    v
Idempotent persistence  recordHash + fingerprint layers (section 21)
    |
    v
Canonical Transactions (MongoDB)
    |
    v
Reconciliation service  reconciliation_service.start_run()
    |                   run lifecycle QUEUED -> RUNNING -> COMPLETED/FAILED
    v
Matching engine       app/services/matching/engine.py   (PURE, in-memory)
    |
    v
Matched / Likely Match / Ambiguous / Unmatched / Exception
    |
    v
Persisted evidence     match_candidates, matches, exceptions, runs
```

Layering rule: `router -> service -> repository/domain`. The matching engine is
pure Python — no MongoDB, no network, no clock reads. Given identical inputs
and configuration it produces byte-identical output (`test_reconciliation_is_repeatable_byte_for_byte`).

## 3. Transaction normalization

Canonical transactions store:

- `amount`: always positive, `Decimal` (BSON `Decimal128`). The sign lives in
  `direction`. Signed amounts (`-250.50`) and separate debit/credit columns are
  both normalized by `pipeline.amount_and_direction`; explicit debit/credit
  columns win over signed amounts because sign conventions differ per system.
- `currency`: validated ISO-style 3-letter code from a known set.
- `transaction_date`: a calendar date stored as UTC midnight so a +05:30 or
  other offset shift can never move the financial date.
- `normalized_description` / `normalized_reference` /
  `normalized_counterparty`: canonical forms used for comparison. Originals are
  preserved beside them.
- `transaction_type`, `status`, `source_record_id`, `fingerprint`.

Text normalization rules (`services/normalization/text.py`):

- general text: NFKC -> strip punctuation -> collapse whitespace -> lowercase.
- reference: uppercase alnum tokens concatenated, generic labels
  (REF/REFERENCE/NO/NUM/ID...) dropped. `"NEFT-1234"`, `"ref NEFT 1234"` and
  `"NEFT1234"` all normalize to `NEFT1234`.
- counterparty: legal suffixes stripped
  (PVT/PRIVATE/LTD/LIMITED/LLP/INC/CORP/GMBH/...). `"ABC Pvt Ltd"` and
  `"ABC PRIVATE LIMITED"` both normalize to `abc`.

## 4. Candidate generation

Comparing every A-side transaction against every B-side transaction is O(n*m).
Blocking reduces candidates without losing plausible ones:

- Index B side by `currency -> amount bucket -> transactions`, where a bucket
  is `floor(amount / 100)` (`config.amount_bucket_value`).
- For each A-side transaction, probe buckets within `_bucket_span(amount)`.
  Because the fee tolerance is RELATIVE (2% of the larger amount), the span is
  computed from the maximum fee-plausible difference:
  `max(fee_absolute_tolerance, amount * rel / (1 - rel))`, divided by the
  bucket width and rounded up. Example: an ₹7,840 bank credit vs an ₹8,000
  gateway capture spans buckets 78..80 — a naive ±1-bucket probe would miss
  it; the computed reach does not.
- Candidates additionally must be within `candidate_date_window_days = 10`
  calendar days, so weak-date pairs still receive scored evidence while far
  future/past records cost nothing.
- Failed/cancelled records never enter the candidate index at all.

Candidate lists are sorted by `(-score, partner id)` — total order, no ties on
ordering, fully deterministic.

## 5. Matching algorithm

v1 is pairwise with greedy consumption (`ALGORITHM_VERSION = "ll-v1-pairwise"`):

1. Sort both sides deterministically by `(date, amount, id)`.
2. For each A-side transaction in order: generate candidates, score them,
   classify (section 16).
3. When a decision selects partners (MATCHED / LIKELY_MATCH), those B-side
   transactions become *consumed* and cannot be selected again. This prevents
   one gateway record from matching two identical bank records.
4. Unconsumed B-side records are reported as leftovers; the service persists a
   NEEDS_REVIEW exception for each.

Greedy assignment is order-dependent in theory; because input order is
deterministic, results are reproducible. Global optimization arrives with
many-to-one support (section 23).

## 6. Matching signals

Five components are scored per pair (`matching/scorers.py`). Each returns a
`Decimal` score in [0, 1] plus machine-readable reason notes, or `None` when
the component cannot be compared because data is missing on either side.

| signal | strongest when | notes emitted |
|---|---|---|
| amount | exact equality after Decimal parse | `amount_within_fee_band`, `amount_mismatch` |
| date | same calendar day | `date_outside_tolerance` |
| reference | equal after normalization | `reference_partial` |
| counterparty | equal after suffix stripping | (subset/jaccard values) |
| description | token-set overlap of normalized text | (jaccard value) |

## 7. Scoring

Component curves (all `Decimal`, quantized to 4 places):

- **amount**: diff 0 -> `1.0`. Within the fee band (section 10): linear decay
  `0.85 -> 0.60` across the band. Beyond the band: starts at `0.30` and decays
  linearly to `0` across nine additional band-widths.
- **date** (`days_apart` is symmetric): 0d -> `1.0`, 1d -> `0.90`, then
  `-0.20` per extra day, reaching `0.50` at 3d; beyond tolerance -> `0` with
  note `date_outside_tolerance`.
- **reference**: normalized equality -> `1.0`; otherwise
  `max(jaccard(tokens), SequenceMatcher.ratio())`, floored at `0.90` when one
  side's tokens are a subset of the other's.
- **description**: token-set Jaccard on normalized text — order-insensitive,
  so `"PAYMENT ABC LTD"` vs `"ABC LTD PAYMENT"` scores `1.0`.
- **counterparty**: normalized equality -> `1.0`; token subset -> `0.90`;
  otherwise Jaccard over suffix-stripped tokens.

Composite: weighted average of the five components. Missing data receives a
neutral prior (`missing_component_score = 0.45`) instead of weight
redistribution, so sparse records lose confidence rather than being silently
rewarded. Type compatibility modifiers are applied to the composite afterwards
(section 14).

## 8. Weight configuration

All numbers live in one frozen dataclass, `MatchingConfig`
(`matching/config.py`) — no magic numbers anywhere else:

```python
weight_amount        = 0.35
weight_date          = 0.20
weight_reference     = 0.20
weight_counterparty  = 0.15
weight_description   = 0.10      # sums to 1.00

date_tolerance_days          = 3
candidate_date_window_days   = 10
fee_absolute_tolerance       = 1.00
fee_relative_tolerance       = 0.02
exact_match_threshold        = 0.90
likely_match_threshold       = 0.70
ambiguous_margin             = 0.05
min_corroboration            = 0.50
missing_component_score      = 0.45
amount_bucket_value          = 100.00
```

The effective configuration is serialized into every
`ReconciliationRun.config` at run time, so historical results remain
reproducible even after defaults change. Runs also store
`algorithm_version`; bump it whenever scoring semantics change.

## 9. Date tolerance

Same-day records score highest; ±1 day remains strong (settlement lag); decay
reaches `0.50` at the 3-day edge; beyond 3 days the component contributes
nothing but the pair may still appear as evidence inside the ±10-day candidate
window. There is no asymmetric behaviour around weekends yet (see section 25).

## 10. Amount tolerance

A difference is "fee-plausible" when

```
diff <= max(1.00, 2% of the larger amount)
```

Pairs inside the band can never finalize as automatic MATCHED: they are capped
at LIKELY_MATCH and raise a POSSIBLE_FEE exception naming both records and the
difference (e.g. bank net ₹9,900 vs gateway gross ₹10,000).

## 11. Reference matching

References are identity-grade evidence: after normalization they must be equal
for a full score. Partial overlap still contributes via token Jaccard,
sequence ratio and a subset bonus, but emits `reference_partial` so reviewers
can see confidence came from partial identity. Missing references make the
component unavailable (neutral prior) — a missing UTR must not be treated as a
mismatch, nor as invisible perfection.

## 12. Description matching

Descriptions are noisy free text ("NEFT CREDIT QRS", "QRS LIMITED PAYMENT"),
so they use order-insensitive token-set overlap. Word-order differences are
free; vocabulary differences reduce the score proportionally. Missing on
either side -> neutral prior, never a crash (`test_missing_text_fields_do_not_crash_scoring`).

## 13. Counterparty matching

Counterparties compare on suffix-stripped tokens: `"PI COMMERCE PVT LTD"`
equals `"PI COMMERCE LIMITED"`. Subset relations (one side drops a word) score
`0.90`. Different parties score low, which is what keeps CASE-B-style
amount-only coincidences out of MATCHED.

## 14. Currency handling

Cross-currency monetary matching is **not supported in Phase 2**, by design:

- Candidate generation only probes within the same currency.
- If a record has no same-currency candidates but a different-currency record
  exists within the fee band and date tolerance, the pair becomes an
  EXCEPTION (`UNSUPPORTED_CURRENCY`) instead of a silent non-match — the
  situation is surfaced for review, not hidden.

Type-compatibility modifiers (recorded, never silent):

- REVERSAL vs non-REVERSAL: composite × `0.40` (`reversal_type_mismatch`).
- REFUND vs SALE/PAYMENT: composite × `0.50` (`type_conflict_refund_vs_sale`)
  — a customer refund must never auto-match the original sale even when
  amounts are equal.

Direction semantics: sign conventions differ between systems (bank debit vs
gateway credit for the same event under different bookkeeping). Ingestion
normalizes to absolute amount + direction; the engine records
`directions_agree` / `directions_differ_by_source_semantics` as evidence
rather than rejecting on representation (CASE E, tested).

## 15. Ambiguity detection

After scoring, if another *unconsumed* candidate scores within
`ambiguous_margin` (0.05) of the leader AND both clear
`likely_match_threshold`, the engine refuses to choose: status AMBIGUOUS, no
partners selected, both twins stay available, and a NEEDS_REVIEW exception
preserves every plausible partner id (`ambiguousPartnerIds` in evidence).
This is what keeps twin payments from being arbitrarily paired.

## 16. Classification thresholds

On the composite score of the best unconsumed candidate:

| condition | outcome |
|---|---|
| score < 0.70 | UNMATCHED (evidence kept) |
| corroboration < 0.50 | capped at LIKELY_MATCH (`insufficient_non_amount_evidence`) — amount-only matches cannot auto-finalize |
| in fee band | capped at LIKELY_MATCH + POSSIBLE_FEE exception |
| pending vs settled conflict | capped at LIKELY_MATCH + STATUS_CONFLICT exception |
| ambiguity cluster | AMBIGUOUS, nothing consumed |
| score >= 0.90, margin over runner-up ok, no caps | MATCHED |
| otherwise | LIKELY_MATCH |

`match_type` EXACT requires amount, date AND reference components all equal to
`1.0` plus final status MATCHED; everything else is FUZZY. (MANUAL /
ONE_TO_MANY / MANY_TO_ONE exist as reserved MatchType values.)

Hard pre-filters before any scoring:

- FAILED/CANCELLED records are excluded from matching entirely ->
  EXCEPTION (`FAILED_TRANSACTION`).
- Zero-amount records -> EXCEPTION (`ZERO_AMOUNT`); never auto-matched, never
  auto-deduplicated.

## 17. Match statuses

Per-record/group outcomes (`ReconciliationStatus`):

- `MATCHED` — high confidence, auto-accepted suggestion.
- `LIKELY_MATCH` — probable pairing needing confirmation (fee, status
  conflict, missing evidence, or sub-exact score).
- `AMBIGUOUS` — multiple equally plausible partners; nothing auto-selected.
- `UNMATCHED` — no acceptable candidate found.
- `EXCEPTION` — hard-routed investigation item (failed, zero, currency,
  collision).
- `MANUAL_MATCHED` — reserved for human decisions.

Every non-MATCHED outcome preserves full evidence: score breakdown per
component, reason strings, tolerances used, ambiguous partner ids.

## 18. Exception handling

Exceptions are persisted documents (`exceptions` collection) with
`reasonCode`, `detail`, `status OPEN/RESOLVED/DISMISSED`, and the transaction
ids involved. Current reasons raised by the engine/service:

- `POSSIBLE_FEE` — amounts differ within the fee band.
- `STATUS_CONFLICT` — pending paired with settled.
- `UNSUPPORTED_CURRENCY` — same-looking record in another currency.
- `ZERO_AMOUNT` — zero-value record needs eyes.
- `FAILED_TRANSACTION` — failed/cancelled excluded from matching.
- `CANDIDATE_COLLISION` — reserved.
- `NEEDS_REVIEW` — ambiguity clusters and leftover B-side records.

Run stats report `exceptionCount` as ALL exception items created by the run
(including fee/status items attached to LIKELY_MATCH decisions and leftover
reviews), matching what users will actually see in the review queue.

## 19. Algorithm versioning

`ALGORITHM_VERSION = "ll-v1-pairwise"` is stamped on every run and every
match document. Combined with the frozen config snapshot this makes any
historical decision reproducible and lets future versions coexist with old
data. Bump the version whenever weights, curves or classification change.

## 20. Auditability

For each decision the system stores:

- every considered candidate pair with its full score breakdown and reasons
  (`match_candidates`; capped at 20,000 pairs/run as a safety valve),
- the chosen partner(s), match type, confidence and human-readable reasons on
  the match document, including `matchedFields` / `mismatchedFields`,
- exceptions with their reason codes,
- the run document with algorithm version + config + counters.

Raw imported records are never mutated (`raw_transactions`), so any decision
can be traced back to original file content.

## 21. Idempotency

Three independent layers:

1. **File checksum** — canonical JSON of resolved rows hashed; the unique
   index `(workspaceId, sourceId, checksum)` (partial: excludes rows already
   marked DUPLICATE) makes duplicate imports structurally impossible.
   Re-uploads return `isDuplicate: true` linked to the original and ingest
   nothing.
2. **Record hash** — `(workspaceId, sourceId, recordHash)` unique on raw
   evidence; replayed rows skip canonical creation
   (`skipped_duplicate_count`). The hash includes row ordinal, so genuinely
   identical lines within one file are distinct evidence.
3. **Fingerprint** — source-scoped content hash of the normalized
   transaction. Identical fingerprints never delete anything; they are linked
   bidirectionally as `potential_duplicate_ids` for human review.

Legitimate repeated expenses (same amount/date/description, different provenance)
are kept as separate transactions and merely flagged — deduplication is a
review action, never a silent side effect.

## 22. Workspace isolation

- Every query in every repository leads with `workspaceId`; the value comes
  from server-resolved auth context (`deps.get_current_workspace`), never from
  request bodies/query strings.
- Every financial index leads with `workspaceId`, mirroring isolation in the
  index layout.
- Foreign ids behave exactly like unknown ones (404/invalid), verified for
  sources, files, raw evidence, transactions, runs, matches and exceptions.
- Unique constraints are tenant-scoped: the same file content, source name or
  source-record ids may legitimately exist in two workspaces without
  colliding.

## 23. One-to-many / many-to-one (future)

v1 is pairwise. Settlement splits (bank ₹100,000 vs gateway ₹60,000 + ₹40,000)
currently surface as UNMATCHED legs — intentionally: guessing aggregation
without explicit support would break explainability. The dataset pins this
behaviour (`B-SP-01` scenario) and `MatchType.ONE_TO_MANY` / `MANY_TO_ONE`
are reserved. Planned approach: sum-based grouping proposals emitted as
suggestions for human/AI confirmation, never silent merges.

## 24. Fee scenarios

Covered explicitly: gross-vs-net settlement pairs inside the relative band
(`LIKELY_MATCH` + fee exception, three scenarios in the dataset), an explicit
gateway FEE record type kept as its own economic event, and the absolute
₹1 floor for small-amount differences. Amounts beyond the band decay toward
zero contribution instead of creating false precision.

## 25. Known limitations

- Greedy pairwise consumption is order-dependent in principle; deterministic
  ordering makes it reproducible but not globally optimal.
- No cross-currency matching or FX normalization (surfaced as exceptions).
- Calendar-day granularity only: no intraday timestamps, no weekend/holiday
  settlement-lag modelling beyond fixed day counts.
- Text similarity is lexical (Jaccard/SequenceMatcher); semantic similarity
  ("AMAZON PAY" vs "AMZN*MARKETPLACE") is out of scope until embeddings or
  alias tables are introduced deliberately.
- Reference normalization concatenates alnum tokens; exotic formats carrying
  meaningful internal whitespace could over-collapse.
- One workspace = one owner (no roles/membership yet).
- Synchronous run execution; very large datasets need batching/streaming.
- Candidate cap (20k pairs) skips evidence storage above the threshold rather
  than failing the run.

## 26. Future AI agent integration

The AI agent is an INVESTIGATION layer, not a matching layer:

```
Deterministic Engine
        |
        v
High-confidence matches  (auto-suggested, audit-ready)
        |
Exceptions / ambiguous cases
        |
AI investigation agent
        |- gathers evidence: raw records, history, similar resolved cases
        |- drafts explanation: "why might this exception have occurred?"
        |- suggests resolution(s) with citations to evidence
        v
Human approval (approve / reject / edit)
```

The agent must never assign or alter match decisions directly. It consumes the
engine's stored evidence (score breakdowns, reasons, exceptions) and produces
explanations and suggestions; only deterministic output and human-approved
decisions change reconciliation state. Every agent suggestion will itself be
stored with its own provenance, separate from `ALGORITHM_VERSION`-stamped
decisions.

## Verification against the synthetic dataset

The deterministic synthetic dataset (`app/synthetic/dataset.py`, 146 records
across bank/gateway/accounting) ships with pinned ground truth
(`GROUND_TRUTH`, 45 scenario entries). Verified results (bank vs gateway run,
79 transactions):

| metric | value |
|---|---|
| pinned scenarios | 45 |
| correct classifications | 45 |
| incorrect classifications | 0 |
| breakdown | 25 MATCHED, 8 LIKELY_MATCH, 2 AMBIGUOUS, 6 UNMATCHED, 4 EXCEPTION |

This validates the current algorithm against intentionally constructed
scenarios; it is NOT real-world accuracy. Scenario families covered: exact,
fuzzy-description, date drift, missing references/descriptions, ambiguity
twins, refund-vs-sale conflicts, reversals, fee bands, settlement splits,
pending/failed/zero states, cross-currency mirrors, and unmatched tails on
both sides.
