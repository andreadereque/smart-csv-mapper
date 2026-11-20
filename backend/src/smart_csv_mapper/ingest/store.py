"""In-memory store for uploaded files, with a time-to-live (ADR-008)."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from smart_csv_mapper.ingest.reader import ParsedCsv

DEFAULT_TTL_SECONDS = 3600


@dataclass(frozen=True)
class StoredFile:
    file_id: str
    filename: str
    parsed: ParsedCsv
    stored_at: float
    sha256: str = ""


class FileNotFound(KeyError):
    pass


class FileStore:
    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._files: dict[str, StoredFile] = {}

    def put(self, filename: str, parsed: ParsedCsv, sha256: str = "") -> StoredFile:
        self._evict_expired()
        stored = StoredFile(uuid.uuid4().hex, filename, parsed, self._clock(), sha256)
        self._files[stored.file_id] = stored
        return stored

    def get(self, file_id: str) -> StoredFile:
        self._evict_expired()
        if file_id not in self._files:
            raise FileNotFound(file_id)
        return self._files[file_id]

    def _evict_expired(self) -> None:
        now = self._clock()
        expired = [k for k, f in self._files.items() if now - f.stored_at > self._ttl]
        for key in expired:
            del self._files[key]
