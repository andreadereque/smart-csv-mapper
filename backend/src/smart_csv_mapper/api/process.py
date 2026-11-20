"""Preview and export a file with a reviewed mapping; read the audit log."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from smart_csv_mapper.api.files import get_store, get_stored
from smart_csv_mapper.api.mapping import get_llm
from smart_csv_mapper.audit import AuditEntry, AuditLog
from smart_csv_mapper.cache import Cache
from smart_csv_mapper.export import to_csv
from smart_csv_mapper.ingest.store import FileStore, StoredFile
from smart_csv_mapper.llm.base import LLMProvider
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.pipeline import AIStats, CellError, Pipeline, check_mapping

router = APIRouter(tags=["process"])
DEMO_USER = "demo"  # no authentication in this version (ADR-008); see README
MAX_ERRORS_RETURNED = 100


class PreviewRequest(BaseModel):
    fields: list[FieldMapping]
    rows: int = Field(default=20, ge=1, le=100)


class PreviewResponse(BaseModel):
    rows: list[dict[str, str]]
    errors: list[CellError]
    error_count_by_field: dict[str, int]
    rows_checked: int
    ai_stats: list[AIStats]


class ExportRequest(BaseModel):
    fields: list[FieldMapping]
    skip_invalid: bool = False


def get_cache(request: Request) -> Cache:
    cache: Cache = request.app.state.cache
    return cache


def get_audit(request: Request) -> AuditLog:
    audit: AuditLog = request.app.state.audit
    return audit


def _checked(stored: StoredFile, fields: list[FieldMapping]) -> None:
    problems = check_mapping(fields, stored.parsed.headers)
    if problems:
        raise HTTPException(422, {"code": "invalid_mapping", "problems": problems})


@router.post("/files/{file_id}/preview")
async def preview(
    file_id: str,
    body: PreviewRequest,
    store: Annotated[FileStore, Depends(get_store)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    cache: Annotated[Cache, Depends(get_cache)],
) -> PreviewResponse:
    """Transform only the first rows, so the preview stays fast even with AI transforms."""
    stored = get_stored(file_id, store)
    _checked(stored, body.fields)
    result = await Pipeline(llm, cache).run(stored.parsed, body.fields, limit=body.rows)
    counts: dict[str, int] = {}
    for error in result.errors:
        counts[error.field] = counts.get(error.field, 0) + 1
    return PreviewResponse(
        rows=result.rows,
        errors=result.errors,
        error_count_by_field=counts,
        rows_checked=len(result.rows),
        ai_stats=result.ai_stats,
    )


@router.post("/files/{file_id}/export", response_model=None)
async def export(
    file_id: str,
    body: ExportRequest,
    store: Annotated[FileStore, Depends(get_store)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    cache: Annotated[Cache, Depends(get_cache)],
    audit: Annotated[AuditLog, Depends(get_audit)],
) -> Response:
    stored = get_stored(file_id, store)
    _checked(stored, body.fields)
    result = await Pipeline(llm, cache).run(stored.parsed, body.fields)
    invalid = result.invalid_rows()
    if invalid and not body.skip_invalid:
        raise HTTPException(
            422,
            {
                "code": "invalid_rows",
                "invalid_row_count": len(invalid),
                "errors": [e.model_dump() for e in result.errors[:MAX_ERRORS_RETURNED]],
            },
        )
    rows = [row for n, row in enumerate(result.rows, start=1) if n not in invalid]
    audit.append(
        AuditEntry(
            user=DEMO_USER,
            filename=stored.filename,
            file_sha256=stored.sha256,
            rows_total=len(result.rows),
            rows_exported=len(rows),
            rows_skipped=len(invalid),
            mapping=[f.model_dump() for f in body.fields],
            model=llm.model,
            ai_stats=[s.model_dump() for s in result.ai_stats],
        )
    )
    name = stored.filename.rsplit(".", 1)[0] + "_clean.csv"
    return Response(
        content=to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Rows-Exported": str(len(rows)),
            "X-Rows-Skipped": str(len(invalid)),
        },
    )


@router.get("/audit")
def read_audit(audit: Annotated[AuditLog, Depends(get_audit)]) -> list[AuditEntry]:
    return audit.recent()
