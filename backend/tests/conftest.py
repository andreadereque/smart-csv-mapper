from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smart_csv_mapper.config import Settings
from smart_csv_mapper.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_provider="fake",
        max_upload_mb=1,
        max_rows=100,
        audit_db_path=str(tmp_path / "audit.sqlite"),
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()
