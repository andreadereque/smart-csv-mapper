"""FastAPI app factory."""

from fastapi import FastAPI

from smart_csv_mapper import __version__
from smart_csv_mapper.api import health
from smart_csv_mapper.config import Settings, get_settings
from smart_csv_mapper.logging import configure_logging, request_id_middleware


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="smart-csv-mapper", version=__version__)
    app.middleware("http")(request_id_middleware)
    app.include_router(health.router)
    return app
