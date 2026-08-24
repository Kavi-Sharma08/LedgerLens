from pydantic import BaseModel


class FilePublic(BaseModel):
    id: str
    sourceId: str
    fileName: str
    mimeType: str | None = None
    fileSize: int | None = None
    status: str
    checksum: str | None = None
    periodStart: str | None = None
    periodEnd: str | None = None
    transactionCount: int = 0
    skippedDuplicateCount: int = 0
    errorCount: int = 0
    error: str | None = None
    duplicateOfId: str | None = None
    uploadedAt: str | None = None
    processedAt: str | None = None


class FileUploadResponse(BaseModel):
    file: FilePublic
    isDuplicate: bool = False
