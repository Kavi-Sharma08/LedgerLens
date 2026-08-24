from dataclasses import dataclass, field
from datetime import datetime

from bson import ObjectId

from .user import utcnow


@dataclass
class RawTransaction:
    """The original extracted record, preserved verbatim.

    Never mutated, never normalized in place. Every canonical transaction
    traces back here for debugging, audit and reprocessing."""

    workspace_id: ObjectId
    source_id: ObjectId
    source_file_id: ObjectId

    ordinal: int                       # position within the file (0-based)
    raw_data: dict                     # original extracted fields exactly as parsed
    record_hash: str = ""              # idempotency key (see fingerprint module)
    source_record_id: str | None = None
    imported_at: datetime | None = None
    id: ObjectId | None = None

    def to_document(self) -> dict:
        return {
            "workspaceId": self.workspace_id,
            "sourceId": self.source_id,
            "sourceFileId": self.source_file_id,
            "ordinal": self.ordinal,
            "sourceRecordId": self.source_record_id,
            "recordHash": self.record_hash,
            "rawData": self.raw_data,
            "importedAt": self.imported_at or utcnow(),
        }

    @classmethod
    def from_document(cls, doc: dict) -> "RawTransaction":
        return cls(
            id=doc["_id"],
            workspace_id=doc["workspaceId"],
            source_id=doc["sourceId"],
            source_file_id=doc["sourceFileId"],
            ordinal=doc.get("ordinal", 0),
            source_record_id=doc.get("sourceRecordId"),
            record_hash=doc.get("recordHash", ""),
            raw_data=doc.get("rawData") or {},
            imported_at=doc.get("importedAt"),
        )
