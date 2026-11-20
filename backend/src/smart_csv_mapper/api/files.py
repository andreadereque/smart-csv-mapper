"""Upload a CSV and read back its column profile."""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from smart_csv_mapper.config import Settings
from smart_csv_mapper.ingest.errors import IngestError
from smart_csv_mapper.ingest.profile import ColumnProfile, profile_columns
from smart_csv_mapper.ingest.reader import parse_csv
from smart_csv_mapper.ingest.store import FileNotFound, FileStore, StoredFile

ALLOWED_EXTENSIONS = (".csv", ".tsv", ".txt")

router = APIRouter(prefix="/files", tags=["files"])


class FileProfile(BaseModel):
    file_id: str
    filename: str
    encoding: str
    delimiter: str
    row_count: int
    columns: list[ColumnProfile]


def get_store(request: Request) -> FileStore:
    store: FileStore = request.app.state.file_store
    return store


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def to_profile(stored: StoredFile) -> FileProfile:
    parsed = stored.parsed
    return FileProfile(
        file_id=stored.file_id,
        filename=stored.filename,
        encoding=parsed.encoding,
        delimiter=parsed.delimiter,
        row_count=len(parsed.rows),
        columns=profile_columns(parsed),
    )


@router.post("", status_code=201)
async def upload_file(
    file: UploadFile,
    store: Annotated[FileStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> FileProfile:
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise IngestError("unsupported_file_type", "Upload a .csv, .tsv or .txt file.")
    limit = settings.max_upload_mb * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"The file is larger than {settings.max_upload_mb} MB.")
    parsed = parse_csv(raw, settings.max_rows)
    return to_profile(store.put(filename, parsed, hashlib.sha256(raw).hexdigest()))


@router.get("/{file_id}")
def get_file(file_id: str, store: Annotated[FileStore, Depends(get_store)]) -> FileProfile:
    return to_profile(get_stored(file_id, store))


def get_stored(file_id: str, store: FileStore) -> StoredFile:
    try:
        return store.get(file_id)
    except FileNotFound:
        raise HTTPException(404, "File not found or expired.") from None
