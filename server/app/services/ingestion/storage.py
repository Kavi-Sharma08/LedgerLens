"""File storage abstraction.

The domain model never touches disk or object storage directly: it only sees
a `storage_key`. The local-disk backend below serves development; swapping in
S3/GCS later means implementing this interface — no model changes."""

import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class StorageError(Exception):
    pass


class StorageBackend(ABC):
    @abstractmethod
    def save(self, workspace_id: str, original_file_name: str, content: bytes) -> tuple[str, int]:
        """Persist bytes; returns (storage_key, size)."""

    @abstractmethod
    def open(self, storage_key: str) -> bytes:
        """Load bytes for a key."""


class LocalStorageBackend(StorageBackend):
    """Development backend. Keys are opaque UUID paths; the original filename
    is never part of the key (no path traversal, no collisions)."""

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def _resolve(self, storage_key: str) -> Path:
        candidate = (self.base_dir / storage_key).resolve()
        if not str(candidate).startswith(str(self.base_dir.resolve())):
            raise StorageError("Invalid storage key.")
        return candidate

    def save(self, workspace_id: str, original_file_name: str, content: bytes) -> tuple[str, int]:
        directory = self.base_dir / workspace_id
        try:
            directory.mkdir(parents=True, exist_ok=True)
            key = f"{workspace_id}/{uuid.uuid4().hex}"
            path = self._resolve(key)
            path.write_bytes(content)
            return key, len(content)
        except OSError as exc:
            raise StorageError("Could not store the uploaded file.") from exc

    def open(self, storage_key: str) -> bytes:
        try:
            return self._resolve(storage_key).read_bytes()
        except OSError as exc:
            raise StorageError("Could not read the stored file.") from exc


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _backend
    if _backend is None:
        base_dir = os.environ.get("LEDGERLENS_UPLOAD_DIR", "./data/uploads")
        _backend = LocalStorageBackend(base_dir)
    return _backend


def set_storage(backend: StorageBackend) -> None:
    """Test seam."""
    global _backend
    _backend = backend
