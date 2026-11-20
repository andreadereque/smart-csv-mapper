"""Column profiles: what the LLM (and the user) see instead of the whole file."""

from pydantic import BaseModel

from smart_csv_mapper.ingest.reader import ParsedCsv

SAMPLE_SIZE = 5


class ColumnProfile(BaseModel):
    name: str
    samples: list[str]
    distinct_count: int
    empty_ratio: float


def profile_columns(parsed: ParsedCsv) -> list[ColumnProfile]:
    profiles = []
    total = len(parsed.rows)
    for index, name in enumerate(parsed.headers):
        values = [row[index].strip() for row in parsed.rows]
        non_empty = [v for v in values if v]
        distinct = list(dict.fromkeys(non_empty))
        profiles.append(
            ColumnProfile(
                name=name,
                samples=distinct[:SAMPLE_SIZE],
                distinct_count=len(distinct),
                empty_ratio=round((total - len(non_empty)) / total, 3),
            )
        )
    return profiles
