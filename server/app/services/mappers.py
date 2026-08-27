"""Mapping helpers: internal models -> public API payloads."""

from decimal import Decimal

from ..models.match import Match
from ..models.reconciliation_exception import ReconciliationException
from ..models.reconciliation_run import ReconciliationRun
from ..models.source import Source
from ..models.source_file import SourceFile
from ..models.transaction import Transaction
from .normalization.money import money_to_str
from ..schemas.reconciliation import (
    ExceptionPublic,
    MatchPublic,
    RunPublic,
)
from ..schemas.source import SourcePublic
from ..schemas.file import FilePublic
from ..schemas.transaction import TransactionPublic
from ..schemas.user import UserPublic, WorkspacePublic


def to_user_public(user) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        name=user.name,
        email=user.email,
        avatar=user.avatar,
    )


def to_workspace_public(workspace) -> WorkspacePublic | None:
    if workspace is None or workspace.id is None:
        return None
    return WorkspacePublic(
        id=str(workspace.id),
        name=workspace.name,
        slug=workspace.slug,
        rolePermissions=workspace.role_permissions,
        ownerId=str(workspace.owner_id) if workspace.owner_id else None,
    )


def to_exception_public_with_assignee(exc) -> ExceptionPublic:
    """Extend exception mapper to include assignment and notes fields."""
    base = to_exception_public(exc)
    # Add extra fields if present on the model
    data = base.model_dump()
    data["assignedTo"] = getattr(exc, "assigned_to", None)
    data["assignedAt"] = getattr(exc, "assigned_at", None).isoformat() if getattr(exc, "assigned_at", None) else None
    data["resolvedBy"] = getattr(exc, "resolved_by", None)
    data["resolvedAt"] = getattr(exc, "resolved_at", None).isoformat() if getattr(exc, "resolved_at", None) else None
    data["notes"] = getattr(exc, "notes", None) or []
    return data


def _date_str(value) -> str | None:
    return value.isoformat() if value is not None else None


def to_source_public(source: Source) -> SourcePublic:
    return SourcePublic(
        id=str(source.id),
        name=source.name,
        type=source.type.value,
        institution=source.institution,
        accountIdentifier=source.account_identifier,
        currency=source.currency,
        status=source.status.value,
        metadata=source.metadata or {},
        createdAt=source.created_at.isoformat() if source.created_at else None,
    )


def to_file_public(source_file: SourceFile) -> FilePublic:
    duplicate_of = str(source_file.duplicate_of_id) if source_file.duplicate_of_id else None
    return FilePublic(
        id=str(source_file.id),
        sourceId=str(source_file.source_id),
        fileName=source_file.original_file_name,
        mimeType=source_file.mime_type,
        fileSize=source_file.file_size,
        status=source_file.status.value,
        checksum=source_file.checksum[:12],
        periodStart=_date_str(source_file.period_start),
        periodEnd=_date_str(source_file.period_end),
        transactionCount=source_file.transaction_count,
        skippedDuplicateCount=source_file.skipped_duplicate_count,
        errorCount=source_file.error_count,
        error=source_file.error,
        duplicateOfId=duplicate_of,
        uploadedAt=source_file.uploaded_at.isoformat() if source_file.uploaded_at else None,
        processedAt=source_file.processed_at.isoformat() if source_file.processed_at else None,
    )


def to_transaction_public(txn: Transaction) -> TransactionPublic:
    return TransactionPublic(
        id=str(txn.id),
        sourceId=str(txn.source_id),
        sourceFileId=str(txn.source_file_id),
        rawTransactionId=str(txn.raw_transaction_id),
        sourceRecordId=txn.source_record_id,
        transactionDate=_date_str(txn.transaction_date),
        postedDate=_date_str(txn.posted_date),
        amount=money_to_str(Decimal(txn.amount)) if txn.amount is not None else None,
        currency=txn.currency,
        direction=txn.direction.value,
        description=txn.description,
        reference=txn.reference,
        counterparty=txn.counterparty,
        accountIdentifier=txn.account_identifier,
        transactionType=txn.transaction_type,
        status=txn.status,
        potentialDuplicates=[str(i) for i in (txn.potential_duplicate_ids or [])],
        metadata=txn.metadata or {},
        fingerprint=txn.fingerprint or "",
        createdAt=txn.created_at.isoformat() if txn.created_at else None,
    )


def _scope_date_str(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        # datetime -> date portion (dates are stored as UTC midnight)
        return value.date().isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def to_run_public(run: ReconciliationRun) -> RunPublic:
    scope = run.transaction_scope or {}
    started_at = run.started_at.isoformat() if run.started_at else None
    completed_at = run.completed_at.isoformat() if run.completed_at else None
    return RunPublic(
        id=str(run.id),
        status=run.status.value,
        sourceIds=[str(s) for s in (run.source_ids or [])],
        dateFrom=_scope_date_str(scope.get("dateFrom")),
        dateTo=_scope_date_str(scope.get("dateTo")),
        totalTransactions=run.total_transactions,
        matchedCount=run.matched_count,
        likelyMatchCount=run.likely_match_count,
        ambiguousCount=run.ambiguous_count,
        unmatchedCount=run.unmatched_count,
        exceptionCount=run.exception_count,
        algorithmVersion=run.algorithm_version,
        config=run.config or {},
        error=run.error,
        startedAt=started_at,
        completedAt=completed_at,
    )


def to_match_public(match: Match) -> MatchPublic:
    evidence = match.evidence or {}
    confidence = Decimal(match.confidence) if match.confidence is not None else None
    human = match.human_decision or None
    return MatchPublic(
        id=str(match.id),
        reconciliationRunId=str(match.reconciliation_run_id),
        transactionIds=[str(t) for t in (match.transaction_ids or [])],
        matchType=match.match_type.value,
        status=match.status,
        confidence=money_to_str(confidence) if confidence is not None else None,
        scoreBreakdown=evidence.get("scoreBreakdown") or {},
        reasons=evidence.get("reasons") or [],
        matchedFields=evidence.get("matchedFields") or [],
        mismatchedFields=evidence.get("mismatchedFields") or [],
        algorithmVersion=match.algorithm_version,
        algorithmDecision=match.algorithm_decision or match.status,
        humanDecision=human,
        createdAt=match.created_at.isoformat() if match.created_at else None,
    )


def to_exception_public(exc: ReconciliationException) -> ExceptionPublic:
    resolution = exc.resolution or None
    return ExceptionPublic(
        id=str(exc.id),
        reconciliationRunId=str(exc.reconciliation_run_id),
        transactionIds=[str(t) for t in (exc.transaction_ids or [])],
        reasonCode=exc.reason_code.value,
        detail=exc.detail,
        status=exc.status.value,
        resolution=resolution,
        createdAt=exc.created_at.isoformat() if exc.created_at else None,
    )
