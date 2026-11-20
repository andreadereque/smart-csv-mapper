"""Apply a (user-reviewed) mapping to the rows: transform, validate, find duplicates."""

from dataclasses import dataclass, field

from pydantic import BaseModel

from smart_csv_mapper.ai_transforms.split_name import NameSplitter, SplitOutcome, TransformStats
from smart_csv_mapper.cache import Cache
from smart_csv_mapper.ingest.reader import ParsedCsv
from smart_csv_mapper.llm.base import LLMProvider
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.schema import FIELDS_BY_NAME, TARGET_SCHEMA, validate_value
from smart_csv_mapper.transforms.catalog import CATALOG, apply, check_params
from smart_csv_mapper.transforms.result import Err, Ok, Result

SPLIT_PARTS = {"split_name_first": "first", "split_name_last": "last"}


class CellError(BaseModel):
    row: int  # 1-based data row number, as a person would count it
    field: str
    value: str
    reason: str


class AIStats(BaseModel):
    transform: str
    source: str
    rows: int
    distinct: int
    cache_hits: int
    llm_calls: int
    failed: int
    ms: int


@dataclass
class TransformedRows:
    rows: list[dict[str, str]] = field(default_factory=list)
    errors: list[CellError] = field(default_factory=list)
    ai_stats: list[AIStats] = field(default_factory=list)

    def invalid_rows(self) -> set[int]:
        return {e.row for e in self.errors}


def check_mapping(fields: list[FieldMapping], headers: list[str]) -> list[str]:
    """Problems with a mapping sent by the UI (it may use any transform, not just LLM ones)."""
    problems = []
    targets = [f.target for f in fields]
    for name in FIELDS_BY_NAME:
        if name not in targets:
            problems.append(f"{name}: missing from the mapping")
    for item in fields:
        if item.target not in FIELDS_BY_NAME:
            problems.append(f"unknown target field {item.target!r}")
            continue
        if item.source is not None and item.source not in headers:
            problems.append(f"{item.target}: column {item.source!r} does not exist")
        spec = CATALOG.get(item.transform)
        if spec is None:
            problems.append(f"{item.target}: unknown transform {item.transform!r}")
            continue
        problem = check_params(spec, item.params)
        if problem is not None:
            problems.append(f"{item.target}: {problem}")
    return problems


class Pipeline:
    def __init__(self, llm: LLMProvider, cache: Cache) -> None:
        self._splitter = NameSplitter(llm, cache)

    async def run(
        self, parsed: ParsedCsv, fields: list[FieldMapping], limit: int | None = None
    ) -> TransformedRows:
        rows = parsed.rows
        if limit is not None:
            rows = rows[:limit]
        by_target = {f.target: f for f in fields}
        out = TransformedRows(rows=[{} for _ in rows])
        splits: dict[str, SplitOutcome] = {}
        for target in TARGET_SCHEMA:
            mapping = by_target[target.name]
            values = [""] * len(rows)
            if mapping.source is not None:
                index = parsed.headers.index(mapping.source)
                values = [row[index] for row in rows]
            results = await self._column(mapping, values, splits, out)
            for number, (value, result) in enumerate(zip(values, results, strict=True), start=1):
                final = _validated(target.name, result)
                if isinstance(final, Ok):
                    out.rows[number - 1][target.name] = final.value
                else:
                    out.rows[number - 1][target.name] = ""
                    out.errors.append(
                        CellError(row=number, field=target.name, value=value, reason=final.reason)
                    )
        _flag_duplicate_ids(out)
        return out

    async def _column(
        self,
        mapping: FieldMapping,
        values: list[str],
        splits: dict[str, SplitOutcome],
        out: TransformedRows,
    ) -> list[Result]:
        part = SPLIT_PARTS.get(mapping.transform)
        if part is None or mapping.source is None:
            return [apply(mapping.transform, v, mapping.params) for v in values]
        if mapping.source not in splits:
            outcome = await self._splitter.split(values)
            splits[mapping.source] = outcome
            out.ai_stats.append(_ai_stats("split_name", mapping.source, outcome.stats))
        return [splits[mapping.source].result(v, part) for v in values]


def _validated(field_name: str, result: Result) -> Result:
    if isinstance(result, Err):
        return result
    return validate_value(field_name, result.value)


def _flag_duplicate_ids(out: TransformedRows) -> None:
    first_seen: dict[str, int] = {}
    for number, row in enumerate(out.rows, start=1):
        external_id = row["external_id"]
        if external_id == "":
            continue
        if external_id in first_seen:
            out.errors.append(
                CellError(
                    row=number,
                    field="external_id",
                    value=external_id,
                    reason=f"duplicate external_id (first seen in row {first_seen[external_id]})",
                )
            )
            continue
        first_seen[external_id] = number


def _ai_stats(transform: str, source: str, stats: TransformStats) -> AIStats:
    return AIStats(transform=transform, source=source, **stats.__dict__)
