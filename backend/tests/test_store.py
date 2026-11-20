import pytest

from smart_csv_mapper.ingest.reader import ParsedCsv
from smart_csv_mapper.ingest.store import FileNotFound, FileStore

PARSED = ParsedCsv(headers=["a"], rows=[["1"]], encoding="utf-8", delimiter=",")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_put_then_get_returns_the_same_file() -> None:
    store = FileStore()
    stored = store.put("a.csv", PARSED)
    assert store.get(stored.file_id) == stored
    assert stored.filename == "a.csv"


def test_unknown_id_raises_not_found() -> None:
    with pytest.raises(FileNotFound):
        FileStore().get("nope")


def test_files_expire_after_the_ttl_but_not_before() -> None:
    clock = FakeClock()
    store = FileStore(ttl_seconds=60, clock=clock)
    stored = store.put("a.csv", PARSED)
    clock.now = 60
    assert store.get(stored.file_id) == stored
    clock.now = 61
    with pytest.raises(FileNotFound):
        store.get(stored.file_id)
