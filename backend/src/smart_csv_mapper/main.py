"""FastAPI app factory."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from smart_csv_mapper import __version__
from smart_csv_mapper.api import catalog, files, health
from smart_csv_mapper.config import Settings, get_settings
from smart_csv_mapper.ingest.errors import IngestError
from smart_csv_mapper.ingest.store import FileStore
from smart_csv_mapper.logging import configure_logging, request_id_middleware


async def ingest_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, IngestError)
    return JSONResponse(status_code=422, content={"code": exc.code, "detail": exc.message})


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="smart-csv-mapper", version=__version__)
    app.state.settings = settings
    app.state.file_store = FileStore()
    app.middleware("http")(request_id_middleware)
    app.add_exception_handler(IngestError, ingest_error_handler)
    app.include_router(health.router)
    app.include_router(files.router)
    app.include_router(catalog.router)
    return app
