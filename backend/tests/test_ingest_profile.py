from smart_csv_mapper.ingest.profile import SAMPLE_SIZE, profile_columns
from smart_csv_mapper.ingest.reader import ParsedCsv


def _parsed(rows: list[list[str]]) -> ParsedCsv:
    return ParsedCsv(headers=["name", "email"], rows=rows, encoding="utf-8", delimiter=",")


def test_profile_counts_distinct_and_empty_values() -> None:
    rows = [["Ana", "a@x.com"], ["Ana", ""], [" Luis ", "  "], ["Eva", "e@x.com"]]
    name, email = profile_columns(_parsed(rows))
    assert name.samples == ["Ana", "Luis", "Eva"]
    assert name.distinct_count == 3
    assert name.empty_ratio == 0
    assert email.samples == ["a@x.com", "e@x.com"]
    assert email.empty_ratio == 0.5


def test_profile_keeps_only_a_few_samples() -> None:
    rows = [[f"name-{i}", ""] for i in range(20)]
    name, email = profile_columns(_parsed(rows))
    assert len(name.samples) == SAMPLE_SIZE
    assert name.samples[0] == "name-0"
    assert name.distinct_count == 20
    assert email.samples == []
    assert email.empty_ratio == 1
