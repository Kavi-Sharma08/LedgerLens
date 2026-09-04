"""Source & file application services.

Keeps routes thin: validation, duplicate handling and pipeline wiring live
here. Workspace isolation comes from the caller-supplied trusted context."""

import logging

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core.errors import DuplicateFileError, InvalidFileError, SourceNotFoundError
from ..models.enums import FileStatus
from ..models.source import Source
from ..models.source_file import SourceFile
from ..repositories import (
    raw_transaction_repository,
    source_file_repository,
    source_repository,
    transaction_repository,
)
from ..services.normalization.fingerprint import compute_file_checksum
from .ingestion import extraction as content_extraction
from .ingestion import pipeline

logger = logging.getLogger("ledgerlens.sources")

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MiB guard for development phase


async def create_source(db, workspace_id: ObjectId, *, name: str, source_type, institution=None,
                        account_identifier=None, currency="INR", metadata=None) -> Source:
    source = Source(
        workspace_id=workspace_id,
        name=name,
        type=source_type,
        institution=institution,
        account_identifier=account_identifier,
        currency=currency,
        metadata=metadata or {},
    )
    return await source_repository.create_source(db, workspace_id, source)


async def upload_source_file(
    db,
    workspace_id: ObjectId,
    *,
    source: Source,
    file_name: str,
    mime_type: str | None,
    content: bytes,
    uploaded_by: ObjectId | None,
) -> pipeline.IngestionSummary:
    """Full upload flow:

    extract -> checksum -> duplicate check -> persist file -> ingest records.
    Duplicate imports return the original file information with
    `is_duplicate=True` and perform zero ingestion side effects."""
    if len(content) == 0:
        raise InvalidFileError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise InvalidFileError("The uploaded file is too large.")

    extracted = content_extraction.extract(content, file_name, mime_type)
    if extracted.is_empty:
        raise InvalidFileError("No financial records were found in this file.")

    resolved_rows = [content_extraction.resolve_fields(row) for row in extracted.records]
    checksum = compute_file_checksum(
        content_extraction.canonical_records_json(resolved_rows)
    )

    existing = await source_file_repository.find_by_checksum(
        db, workspace_id, source.id, checksum
    )
    if existing is not None:
        # Idempotent re-upload: record the attempt (status DUPLICATE, linked
        # to the original) and ingest nothing.
        duplicate_row = SourceFile(
            workspace_id=workspace_id,
            source_id=source.id,
            file_name=file_name,
            original_file_name=file_name,
            checksum=checksum,
            mime_type=mime_type,
            file_size=len(content),
            status=FileStatus.DUPLICATE,
            uploaded_by=uploaded_by,
            duplicate_of_id=existing.id,
        )
        try:
            await db["source_files"].insert_one(duplicate_row.to_document())
        except DuplicateKeyError as exc:
            logger.warning(
                "duplicate-file row collided for workspace=%s source=%s (%s)",
                workspace_id, source.id, exc,
            )
        logger.info(
            "duplicate upload rejected workspace=%s source=%s originalFile=%s",
            workspace_id, source.id, existing.id,
        )
        return pipeline.IngestionSummary(file=duplicate_row)

    source_file = SourceFile(
        workspace_id=workspace_id,
        source_id=source.id,
        file_name=file_name,
        original_file_name=file_name,
        checksum=checksum,
        mime_type=mime_type,
        file_size=len(content),
        status=FileStatus.UPLOADED,
        uploaded_by=uploaded_by,
    )

    # The (workspaceId, sourceId, checksum) unique index is the concurrency
    # source of truth for parallel uploads of identical content.
    try:
        source_file = await source_file_repository.create_file(db, workspace_id, source_file)
    except DuplicateKeyError:
        raise DuplicateFileError() from None

    summary = await pipeline.ingest_extracted(db, workspace_id, source, source_file, extracted)
    logger.info(
        "file ingested workspace=%s source=%s file=%s processed=%d skipped=%d errors=%d",
        workspace_id, source.id, source_file.id,
        summary.processed_count, summary.skipped_duplicate_count, summary.error_count,
    )
    return summary


async def update_source(
    db,
    workspace_id: ObjectId,
    source_id: ObjectId,
    *,
    name: str | None = None,
    institution: str | None = None,
    currency: str | None = None,
) -> Source:
    """Update a source's mutable fields.

    Raises SourceNotFoundError if the source doesn't exist or belongs to
    another workspace. Raises DuplicateSourceError on name collision."""
    source = await source_repository.get_by_id(db, workspace_id, source_id)
    updated = await source_repository.update_source(
        db, workspace_id, source.id,
        name=name, institution=institution, currency=currency,
    )
    if updated is None:
        raise SourceNotFoundError()
    return updated


async def delete_source(db, workspace_id: ObjectId, source_id: ObjectId) -> None:
    """Delete a source and all associated data (files, raw transactions,
    transactions). Reconciliation run history is preserved as audit context."""
    source = await source_repository.get_by_id(db, workspace_id, source_id)

    raw_deleted = await raw_transaction_repository.delete_by_source(db, workspace_id, source.id)
    txn_deleted = await transaction_repository.delete_by_source(db, workspace_id, source.id)
    files_deleted = await source_file_repository.delete_by_source(db, workspace_id, source.id)
    await source_repository.delete_source(db, workspace_id, source.id)

    logger.info(
        "source deleted workspace=%s source=%s files=%d txns=%d raws=%d",
        workspace_id, source.id, files_deleted, txn_deleted, raw_deleted,
    )
