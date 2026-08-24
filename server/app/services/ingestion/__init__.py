"""Ingestion package: extraction, storage, normalization pipeline."""

from .extraction import ExtractedFile, extract, resolve_fields
from .pipeline import IngestionSummary, RowError, ingest_extracted, normalize_row
from .storage import LocalStorageBackend, StorageBackend, StorageError, get_storage

__all__ = [
    "ExtractedFile",
    "extract",
    "resolve_fields",
    "IngestionSummary",
    "RowError",
    "ingest_extracted",
    "normalize_row",
    "LocalStorageBackend",
    "StorageBackend",
    "StorageError",
    "get_storage",
]
