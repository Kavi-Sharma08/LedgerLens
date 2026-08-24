from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from ..services.normalization.dates import to_utc_midnight
from .enums import FileStatus
from .user import utcnow


@dataclass
class SourceFile:
    """One imported financial document. Binary content lives behind the
    storage interface (storageKey), never inside MongoDB."""

    workspace_id: ObjectId
    source_id: ObjectId

    file_name: str
    original_file_name: str
    checksum: str

    mime_type: str | None = None
    file_size: int | None = None
    storage_key: str | None = None
    status: FileStatus = FileStatus.UPLOADED
    period_start: object | None = None  # date | None
    period_end: object | None = None    # date | None
    uploaded_by: ObjectId | None = None
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None
    transaction_count: int = 0
    skipped_duplicate_count: int = 0
    error_count: int = 0
    error: str | None = None
    duplicate_of_id: ObjectId | None = None
    metadata: dict = field(default_factory=dict)
    id: ObjectId | None = None

    def to_document(self) -> dict:
        now = utcnow()
        return {
            "workspaceId": self.workspace_id,
            "sourceId": self.source_id,
            "fileName": self.file_name,
            "originalFileName": self.original_file_name,
            "mimeType": self.mime_type,
            "fileSize": self.file_size,
            "storageKey": self.storage_key,
            "checksum": self.checksum,
            "status": self.status.value if isinstance(self.status, FileStatus) else self.status,
            "periodStart": to_utc_midnight(self.period_start) if self.period_start else None,
            "periodEnd": to_utc_midnight(self.period_end) if self.period_end else None,
            "uploadedBy": self.uploaded_by,
            "uploadedAt": self.uploaded_at or now,
            "processedAt": self.processed_at,
            "transactionCount": self.transaction_count,
            "skippedDuplicateCount": self.skipped_duplicate_count,
            "errorCount": self.error_count,
            "error": self.error,
            "duplicateOfId": self.duplicate_of_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_document(cls, doc: dict) -> "SourceFile":
        period_start = doc.get("periodStart")
        period_end = doc.get("periodEnd")
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            source_id=doc["sourceId"],
            file_name=doc.get("fileName", ""),
            original_file_name=doc.get("originalFileName", ""),
            checksum=doc.get("checksum", ""),
            mime_type=doc.get("mimeType"),
            file_size=doc.get("fileSize"),
            storage_key=doc.get("storageKey"),
            status=FileStatus(doc.get("status", FileStatus.UPLOADED.value)),
            period_start=period_start.date() if period_start else None,
            period_end=period_end.date() if period_end else None,
            uploaded_by=doc.get("uploadedBy"),
            uploaded_at=doc.get("uploadedAt"),
            processed_at=doc.get("processedAt"),
            transaction_count=doc.get("transactionCount", 0),
            skipped_duplicate_count=doc.get("skippedDuplicateCount", 0),
            error_count=doc.get("errorCount", 0),
            error=doc.get("error"),
            duplicate_of_id=doc.get("duplicateOfId"),
            metadata=doc.get("metadata") or {},
        )
