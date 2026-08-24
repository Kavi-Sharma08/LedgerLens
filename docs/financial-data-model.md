# LedgerLens Financial Data Model (Phase 2)

Status: **implemented** (this document is the design record written before code).

## Purpose

This document defines the financial domain model that underpins reconciliation:
provenance from a raw imported file all the way to a match decision, strict
multi-tenant isolation, money that never loses precision, and idempotent
ingestion.

## Entity overview and relationships

```
Workspace (1)
 └──< FinancialSource (N)            one logical origin of records (bank, gateway, ...)
       └──< SourceFile (N)           one imported document (statement CSV, export ...)
             └──< RawTransaction (N)     the original extracted record, never mutated
                   │
                   └──(1:1)──> Transaction (normalized/canonical)
                                  │
ReconciliationRun (1)             │  (transactions are inputs)
 └──< MatchCandidate (N)          │  pairwise scored evidence
      └──> Match (0..N)           │  final decision per group of transactions
      └──> ReconciliationException (0..N)   items needing investigation
```

- Every financial object carries `workspaceId`.
- A canonical **Transaction** always points to exactly one
  **RawTransaction**, which points to the **SourceFile** it came from, which
  belongs to a **FinancialSource**, which belongs to the **Workspace**.
- Raw and normalized transactions are deliberately separate collections:
  normalization rules improve over time; raw evidence must survive every
  reprocess so decisions remain explainable and re-runs are possible.

## Collections

### sources

| field | type | notes |
|---|---|---|
| `_id` | ObjectId | |
| `workspaceId` | ObjectId | tenant key |
| `name` | str | unique per workspace |
| `type` | enum | BANK / PAYMENT_PROCESSOR / ACCOUNTING / CARD / ERP / MANUAL |
| `institution` | str? | e.g. "HDFC Bank", "Stripe" |
| `accountIdentifier` | str? | masked account ref; display-only |
| `currency` | str | ISO-4217 style, 3 uppercase letters |
| `status` | enum | ACTIVE / ARCHIVED |
| `metadata` | object | free-form, provider-specific |
| `createdAt` / `updatedAt` | datetime UTC | |

### source_files

| field | type | notes |
|---|---|---|
| `_id` | ObjectId | |
| `workspaceId` / `sourceId` | ObjectId | provenance |
| `fileName` | str | stored name |
| `originalFileName` | str | as uploaded |
| `mimeType` / `fileSize` | str / int | |
| `storageKey` | str? | opaque key resolved through the storage interface; local disk today, object storage later |
| `checksum` | str | sha256 over the **canonical parsed record stream** (not raw bytes), so cosmetic formatting differences still dedupe |
| `status` | enum | UPLOADED / PROCESSING / PROCESSED / PARTIAL / FAILED / DUPLICATE |
| `periodStart` / `periodEnd` | date? | optional coverage window |
| `uploadedBy` | ObjectId | user id from trusted boundary |
| `uploadedAt` / `processedAt` | datetime | |
| `transactionCount` / `skippedDuplicateCount` / `errorCount` | int | ingestion summary |
| `error` | str? | safe message when FAILED/PARTIAL |
| `duplicateOfId` | ObjectId? | set when checksum matched an existing file |

Binary files are never stored inside MongoDB. `app/services/ingestion/storage.py`
defines a tiny interface (`save` / `open`) with a local-disk implementation for
development; S3/GCS can slot in later without touching the domain model.

### raw_transactions

Preserves the original extracted fields verbatim.

| field | type | notes |
|---|---|---|
| `_id` | ObjectId | |
| `workspaceId` / `sourceId` / `sourceFileId` | ObjectId | provenance chain |
| `ordinal` | int | position of the record within the file |
| `sourceRecordId` | str? | may be absent — never fabricated |
| `recordHash` | sha256 of (`sourceId`, `ordinal`, canonical raw JSON) | unique per workspace+source → replayed files cannot create new evidence rows |
| `rawData` | object | original extracted fields exactly as parsed |
| `importedAt` | datetime | |

### transactions (canonical / normalized)

The most important collection. One canonical row per ingested raw record.

| field | type | notes |
|---|---|---|
| `_id` | ObjectId | |
| `workspaceId` / `sourceId` / `sourceFileId` / `rawTransactionId` | ObjectId | full provenance |
| `sourceRecordId` | str? | passthrough |
| `transactionDate` | datetime (UTC midnight) | financial/business date, date-only semantics preserved |
| `postedDate` | datetime? | settlement/posting date when the source provides it |
| `amount` | Decimal128 | always positive; sign lives in `direction` |
| `currency` | str | validated 3-letter uppercase |
| `direction` | enum | CREDIT / DEBIT |
| `description` | str? | original text |
| `normalizedDescription` | str? | see normalization rules |
| `reference` | str? | original reference |
| `normalizedReference` | str? | uppercase alnum+token form used for comparison |
| `counterparty` | str? | original |
| `normalizedCounterparty` | str? | suffix-stripped token form |
| `accountIdentifier` | str? | |
| `transactionType` | enum? | SALE / PAYMENT / REFUND / REVERSAL / FEE / TRANSFER / ADJUSTMENT (inferred or supplied) |
| `status` | enum | PENDING / SETTLED / FAILED / CANCELLED (default SETTLED) |
| `fingerprint` | sha256 | stable identity of *content* (see idempotency) |
| `metadata` | object | extras that survived validation |
| `potentialDuplicateIds` | array<ObjectId>? | fingerprint collisions across files — detected, never auto-deleted |
| `createdAt` / `updatedAt` | datetime | |

#### Money

Money is `decimal.Decimal` in Python and `Decimal128` in MongoDB. Floats are
never used. Amounts are quantized to the currency's minor-unit exponent
(2 for INR/USD/EUR/GBP, 0 for JPY, ...). The API layer serializes amounts as
**strings** so JSON consumers never get binary-float artifacts.

#### Direction vs sign

Different systems encode the same economic event with opposite signs. The
canonical form is therefore `(amount > 0, direction)`; normalizers convert
signed inputs into this pair using per-source semantics. Matching compares
absolute amounts plus direction context, never signed values alone.

#### Currency

Validated against `[A-Z]{3}` with an ISO-4217 known-code check. Matching only
compares amounts when both currencies are equal; cross-currency pairs become
EXCEPTION (`unsupported_currency`). No conversion is attempted.

#### Dates

Date-only financial dates are parsed to `date` and stored as UTC-midnight
datetimes purely for Mongo range-query friendliness; all logic treats them as
calendar dates so no timezone shift can corrupt them. True timestamps are
normalized to UTC.

### reconciliation_runs

| field | notes |
|---|---|
| `workspaceId`, `sourceIds[]` | scope of the run |
| `transactionScope` | `{dateFrom?, dateTo?}` filter applied on top of sources |
| `status` | QUEUED / RUNNING / COMPLETED / PARTIAL / FAILED |
| `startedAt`, `completedAt` | |
| counts | `totalTransactions`, `matchedCount`, `likelyMatchCount`, `ambiguousCount`, `unmatchedCount`, `exceptionCount` |
| `algorithmVersion` | e.g. `ll-v1-pairwise` — reproducibility anchor |
| `config` | frozen snapshot of the matching configuration actually used |
| `error` | safe message on failure |

### match_candidates

One document per scored pair (kept even when rejected — auditability).

| field | notes |
|---|---|
| `workspaceId`, `reconciliationRunId` | |
| `transactionAId`, `transactionBId` | ordered by (sourceIds order, id) for determinism |
| `score` | Decimal128 0..1 composite |
| `scoreBreakdown` | `{amountScore, dateScore, referenceScore, counterpartyScore, descriptionScore}` — interpretable evidence for the future AI agent |
| `reasons` | list of human-readable strings (fee band, missing reference, ...) |
| `status` | CONSIDERED / SELECTED / REJECTED / AMBIGUOUS |

### matches

| field | notes |
|---|---|
| `workspaceId`, `reconciliationRunId` | |
| `transactionIds[]` | 2 today; array keeps ONE_TO_MANY/MANY_TO_ONE open |
| `matchType` | EXACT / FUZZY / MANUAL / ONE_TO_MANY / MANY_TO_ONE |
| `confidence` | Decimal128 composite score |
| `evidence` | scoreBreakdown, reasons, tolerances used, component scores |
| `algorithmVersion` | copied from run |
| `algorithmDecision` | MATCHED / LIKELY_MATCH ... — never overwritten |
| `humanDecision` | null until review exists (MATCH / REJECT / MARK_EXCEPTION + actor/timestamp) |

### exceptions

Items requiring investigation.

| field | notes |
|---|---|
| `workspaceId`, `reconciliationRunId` | |
| `transactionIds[]` | usually one; ambiguity groups carry several |
| `reasonCode` | UNSUPPORTED_CURRENCY / POSSIBLE_FEE / STATUS_CONFLICT / ZERO_AMOUNT / FAILED_TRANSACTION / NEEDS_REVIEW / CANDIDATE_COLLISION |
| `detail` | human-readable explanation |
| `status` | OPEN / RESOLVED / DISMISSED |
| `resolution` | null until human acts |

## Tenant isolation

- Every repository function takes `workspace_id` as its **first** parameter and
  merges it into the query filter; there is no repository API that can read
  financial rows without it.
- `workspaceId` is **never** accepted from request bodies for financial
  objects. It is resolved server-side: trusted headers → user → owned
  workspace (`api/deps.get_current_workspace`).
- Unique/partial indexes are all compound keys beginning with
  `workspaceId`, so cross-tenant collisions are structurally impossible.
- Tests assert that queries issued contain the workspace predicate and that
  cross-workspace reads return nothing.

## Idempotency & duplicates

Three independent layers (each documented in code):

1. **File level** — `checksum` = sha256 of the canonical parsed record stream.
   Unique index `(workspaceId, sourceId, checksum)`. Re-uploading the same
   content creates a file marked DUPLICATE pointing at the original and
   ingests nothing.
2. **Evidence level** — `raw_transactions.recordHash` = sha256(sourceId,
   ordinal, canonical raw JSON). Unique index `(workspaceId, sourceId,
   recordHash)`. If the same file somehow bypasses the checksum (edited
   headers etc.), replays still cannot duplicate evidence. The ordinal makes
   two legitimately identical lines within one file distinct evidence.
3. **Content level** — transaction `fingerprint` = sha256 over stable
   normalized fields (source, currency, amount, direction, date, normalized
   description/reference/counterparty). NOT unique — a collision flags
   `potentialDuplicateIds` on both documents instead of deleting anything.

Explicit edge-case behaviour:

| case | behaviour |
|---|---|
| same file uploaded twice | second file → DUPLICATE, zero side effects |
| same-looking transaction twice legitimately (two lines) | both kept; ordinals differ → different recordHash |
| two records share amount+date | never treated as duplicates (fingerprint includes description/reference) |
| sourceRecordId missing | ingestion proceeds; fingerprint does not depend on it |
| sourceRecordId changed between exports | new evidence ingested; fingerprint collision links `potentialDuplicateIds` for review |

## Indexes (with rationale)

All compound indexes lead with `workspaceId` because every query is
tenant-scoped first.

| collection | index | why |
|---|---|---|
| users | `(email) unique` | login lookup (existing) |
| workspaces | `(slug) unique`, `(ownerId)` | existing |
| sources | `(workspaceId, name) unique` | name uniqueness per tenant + listing |
| sources | `(workspaceId, type)` | filtered listings |
| source_files | `(workspaceId, sourceId, checksum) unique` | file-level idempotency |
| source_files | `(workspaceId, sourceId, uploadedAt desc)` | "files for source" screens |
| raw_transactions | `(workspaceId, sourceId, recordHash) unique` | evidence-level idempotency |
| raw_transactions | `(workspaceId, sourceFileId)` | reprocessing/debug per file |
| transactions | `(workspaceId, sourceId, fingerprint)` | duplicate detection lookups |
| transactions | `(workspaceId, transactionDate)` | date-range filters & run scoping |
| transactions | `(workspaceId, currency, amount)` | candidate blocking by amount buckets |
| transactions | `(workspaceId, sourceRecordId)` sparse | trace source-record → canonical |
| reconciliation_runs | `(workspaceId, createdAt desc)` | history lists |
| match_candidates | `(reconciliationRunId)` (+ workspaceId in doc) | run-scoped retrieval |
| matches | `(workspaceId, reconciliationRunId)` | run results page |
| exceptions | `(workspaceId, runId)`, `(workspaceId, status)` | review queues |
