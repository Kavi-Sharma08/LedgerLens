"""Reconciliation orchestration.

router -> reconciliation_service -> matching_engine -> repositories

The engine is pure; this module owns the run lifecycle (QUEUED -> RUNNING ->
COMPLETED/FAILED), persistence of candidates/matches/exceptions and the
workspace-scoped loading of transaction scope."""

import logging
from datetime import datetime, timezone

from bson import ObjectId

from ..core.errors import InvalidSourceError, SourceNotFoundError
from ..models.enums import (
    CandidateStatus,
    ExceptionReason,
    ExceptionStatus,
    MatchType,
    ReconciliationStatus,
    RunStatus,
)
from ..models.match import Match
from ..models.match_candidate import MatchCandidate
from ..models.reconciliation_exception import ReconciliationException
from ..models.reconciliation_run import ReconciliationRun
from ..repositories import (
    exception_repository,
    match_repository,
    reconciliation_run_repository,
    source_repository,
    transaction_repository,
)
from .matching import ALGORITHM_VERSION, DEFAULT_MATCHING_CONFIG, MatchingConfig, reconcile

logger = logging.getLogger("ledgerlens.reconciliation")

# Safety valve: a pathological dataset could explode pairwise candidates.
MAX_CANDIDATES_PER_RUN = 20_000


async def list_run_unmatched(
    db,
    workspace_id: ObjectId,
    run_id: ObjectId,
    *,
    limit: int | None = None,
    cursor: str | None = None,
):
    """Transactions from the run's source scope that ended the run without a
    match group (UNMATCHED A-side records; B-side leftovers are exceptions).

    Read-model composition only: scope transactions minus every transaction id
    that appears in one of the run's matches. No engine state is recomputed —
    the persisted run remains the single source of truth."""
    run = await reconciliation_run_repository.get_by_id(db, workspace_id, run_id)

    matched_ids = await match_repository.matched_transaction_ids_for_run(
        db, workspace_id, run.id
    )
    query_filter = transaction_repository.TransactionFilter(exclude_ids=list(matched_ids))
    page = await transaction_repository.list_transactions_for_sources(
        db,
        workspace_id,
        [ObjectId(s) for s in run.source_ids],
        query_filter,
        limit=limit,
        cursor=cursor,
    )
    from .mappers import to_transaction_public

    page.items = [to_transaction_public(t) for t in page.items]
    return page


async def start_run(
    db,
    workspace_id: ObjectId,
    *,
    source_ids: list[ObjectId],
    config: MatchingConfig = DEFAULT_MATCHING_CONFIG,
) -> ReconciliationRun:
    """Run a full synchronous reconciliation over the given sources.

    Sources are validated against the workspace first — a foreign source id
    behaves exactly like an unknown one."""
    if len(source_ids) < 2:
        raise InvalidSourceError("Select at least two sources to reconcile.")

    for source_id in source_ids:
        try:
            await source_repository.get_by_id(db, workspace_id, source_id)
        except SourceNotFoundError:
            # A foreign tenant's source id behaves exactly like an unknown one:
            # the run selection itself is invalid, never a cross-tenant leak.
            raise InvalidSourceError(
                "One of the selected sources doesn't exist in this workspace."
            ) from None

    run = ReconciliationRun(
        workspace_id=workspace_id,
        source_ids=list(source_ids),
        status=RunStatus.QUEUED,
        algorithm_version=ALGORITHM_VERSION,
        config=config.to_dict(),
    )
    run = await reconciliation_run_repository.create_run(db, workspace_id, run)
    await reconciliation_run_repository.mark_running(db, run.id)

    logger.info(
        "reconciliation started run=%s workspace=%s sources=%s algorithm=%s",
        run.id, workspace_id, [str(s) for s in source_ids], ALGORITHM_VERSION,
    )

    try:
        # v1 pairing model: side A = first listed source, side B = everything
        # else combined. Deterministic given the caller's source order.
        primary_source = source_ids[0]
        other_sources = list(source_ids[1:])

        transactions_a = await transaction_repository.list_for_sources(
            db, workspace_id, [primary_source]
        )
        transactions_b = await transaction_repository.list_for_sources(
            db, workspace_id, other_sources
        )

        result = reconcile(transactions_a, transactions_b, config)

        candidates, matches, exceptions = _build_documents(
            workspace_id, run.id, result, config
        )

        inserted_candidates = 0
        if len(candidates) <= MAX_CANDIDATES_PER_RUN:
            inserted_candidates = await match_repository.insert_candidates(db, candidates)
        else:
            logger.warning(
                "candidate set exceeded cap (%d > %d); candidates skipped for run=%s",
                len(candidates), MAX_CANDIDATES_PER_RUN, run.id,
            )
        for match in matches:
            await match_repository.insert_match(db, match)
        await exception_repository.insert_exceptions(db, exceptions)

        stats = dict(result.stats)
        stats["totalTransactions"] = len(transactions_a) + len(transactions_b)
        # Leftover B records each receive a NEEDS_REVIEW exception below.
        stats["exceptionCount"] = stats.get("exceptionCount", 0) + len(result.leftover_b)
        final_status = RunStatus.COMPLETED
        await reconciliation_run_repository.complete_run(db, run.id, stats, final_status)

        logger.info(
            "reconciliation finished run=%s workspace=%s matched=%d likely=%d ambiguous=%d "
            "unmatched=%d exceptions=%d candidates=%d duration_hint=synchronous",
            run.id, workspace_id, stats["matchedCount"], stats["likelyMatchCount"],
            stats["ambiguousCount"], stats["unmatchedCount"], stats["exceptionCount"],
            inserted_candidates,
        )

        refreshed = await reconciliation_run_repository.get_by_id(db, workspace_id, run.id)
        return refreshed

    except Exception as exc:  # noqa: BLE001 - converted into a failed run
        logger.exception("reconciliation failed run=%s workspace=%s", run.id, workspace_id)
        await reconciliation_run_repository.complete_run(
            db,
            run.id,
            {},
            RunStatus.FAILED,
            error="The reconciliation couldn't be completed. Please try again.",
        )
        raise


def _build_documents(workspace_id, run_id, result, config):
    candidates: list[MatchCandidate] = []
    matches: list[Match] = []
    exceptions: list[ReconciliationException] = []
    now = datetime.now(timezone.utc)

    for decision in result.decisions:
        selected_ids = [t.id for t in decision.selected]

        for pair in decision.candidates:
            if pair.transaction_b.id in selected_ids:
                candidate_status = CandidateStatus.SELECTED
            elif decision.status == ReconciliationStatus.AMBIGUOUS:
                candidate_status = CandidateStatus.AMBIGUOUS
            else:
                candidate_status = CandidateStatus.REJECTED
            candidates.append(
                MatchCandidate(
                    workspace_id=workspace_id,
                    reconciliation_run_id=run_id,
                    transaction_a_id=pair.transaction_a.id,
                    transaction_b_id=pair.transaction_b.id,
                    score=pair.score,
                    score_breakdown={k: str(v) for k, v in pair.breakdown.items()},
                    reasons=pair.reasons,
                    status=candidate_status,
                )
            )

        if decision.status == ReconciliationStatus.UNMATCHED:
            continue

        if decision.status in (
            ReconciliationStatus.MATCHED,
            ReconciliationStatus.LIKELY_MATCH,
        ):
            matched_fields, mismatched_fields = _fields_from_breakdown(
                decision.evidence.get("scoreBreakdown", {})
            )
            evidence = {
                **decision.evidence,
                "matchedFields": matched_fields,
                "mismatchedFields": mismatched_fields,
            }
            matches.append(
                Match(
                    workspace_id=workspace_id,
                    reconciliation_run_id=run_id,
                    transaction_ids=[decision.primary.id] + selected_ids,
                    match_type=decision.match_type or MatchType.FUZZY,
                    status=decision.status.value,
                    confidence=decision.confidence,
                    evidence=evidence,
                    algorithm_version=ALGORITHM_VERSION,
                )
            )

        for item in decision.exceptions:
            exceptions.append(
                ReconciliationException(
                    workspace_id=workspace_id,
                    reconciliation_run_id=run_id,
                    transaction_ids=[str(t) for t in item.transaction_ids],
                    reason_code=item.reason_code,
                    detail=item.detail,
                    status=ExceptionStatus.OPEN,
                    created_at=now,
                )
            )

    # Leftover B-side transactions were never selected by any group.
    unmatched_b_exceptions = [
        ReconciliationException(
            workspace_id=workspace_id,
            reconciliation_run_id=run_id,
            transaction_ids=[txn.id],
            reason_code=ExceptionReason.NEEDS_REVIEW,
            detail="No candidate was found for this record during the run.",
            status=ExceptionStatus.OPEN,
            created_at=now,
        )
        for txn in result.leftover_b
    ]
    exceptions.extend(unmatched_b_exceptions)

    return candidates, matches, exceptions


def _fields_from_breakdown(breakdown: dict) -> tuple[list, list]:
    def value(name):
        raw = breakdown.get(name)
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    mapping = {
        "amountScore": "amount",
        "dateScore": "date",
        "referenceScore": "reference",
        "counterpartyScore": "counterparty",
        "descriptionScore": "description",
    }
    matched_fields, mismatched_fields = [], []
    for key, label in mapping.items():
        v = value(key)
        if v is None:
            continue
        if v >= 0.99:
            matched_fields.append(label)
        elif v < 0.5:
            mismatched_fields.append(label)
    return matched_fields, mismatched_fields
