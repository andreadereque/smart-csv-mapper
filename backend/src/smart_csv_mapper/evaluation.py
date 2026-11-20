"""Evals: measure the mapping and the name splitting against hand-labelled cases (ADR-009).

Unit tests use a fake model; `evals/run.py` runs this against a real one and writes a report.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from smart_csv_mapper.ai_transforms.split_name import NameSplitter
from smart_csv_mapper.cache import InMemoryCache
from smart_csv_mapper.ingest.profile import profile_columns
from smart_csv_mapper.ingest.reader import parse_csv
from smart_csv_mapper.llm.base import LLMProvider
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.mapping.suggest import suggest_mapping
from smart_csv_mapper.transforms.result import Ok

Expected = dict[str, dict[str, object]]


@dataclass(frozen=True)
class MappingCase:
    name: str
    raw: bytes
    expected: Expected


@dataclass(frozen=True)
class NameCase:
    input: str
    first: str
    last: str


@dataclass(frozen=True)
class FieldResult:
    case: str
    target: str
    expected: dict[str, object]
    actual: FieldMapping
    source_ok: bool
    full_ok: bool


@dataclass
class MappingReport:
    results: list[FieldResult] = field(default_factory=list)
    latencies_ms: list[int] = field(default_factory=list)
    fallbacks: int = 0
    cases: int = 0

    @property
    def source_accuracy(self) -> float:
        return _ratio(sum(r.source_ok for r in self.results), len(self.results))

    @property
    def full_accuracy(self) -> float:
        return _ratio(sum(r.full_ok for r in self.results), len(self.results))

    def accuracy_by_field(self) -> dict[str, float]:
        by_field: dict[str, list[bool]] = {}
        for result in self.results:
            by_field.setdefault(result.target, []).append(result.full_ok)
        return {k: _ratio(sum(v), len(v)) for k, v in by_field.items()}


@dataclass(frozen=True)
class NameResult:
    case: NameCase
    first: str
    last: str
    ok: bool


@dataclass
class NameReport:
    results: list[NameResult] = field(default_factory=list)
    llm_calls: int = 0
    ms: int = 0

    @property
    def accuracy(self) -> float:
        return _ratio(sum(r.ok for r in self.results), len(self.results))


def _ratio(hits: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(hits / total, 4)


def load_mapping_cases(folder: Path) -> list[MappingCase]:
    cases = []
    for path in sorted(folder.glob("*.csv")):
        expected = json.loads(path.with_suffix(".expected.json").read_text(encoding="utf-8"))
        cases.append(MappingCase(path.stem, path.read_bytes(), expected))
    return cases


def load_name_cases(path: Path) -> list[NameCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [NameCase(**json.loads(line)) for line in lines if line.strip()]


def score_field(case: str, expected: dict[str, object], actual: FieldMapping) -> FieldResult:
    source_ok = actual.source == expected["source"]
    full_ok = source_ok
    if source_ok and expected["source"] is not None:
        full_ok = actual.transform == expected["transform"]
        expected_params = expected.get("params", {})
        assert isinstance(expected_params, dict)
        for key, value in expected_params.items():
            if actual.params.get(key) != value:
                full_ok = False
    return FieldResult(case, actual.target, expected, actual, source_ok, full_ok)


async def evaluate_mapping(cases: list[MappingCase], llm: LLMProvider) -> MappingReport:
    report = MappingReport(cases=len(cases))
    for case in cases:
        columns = profile_columns(parse_csv(case.raw, max_rows=10_000))
        started = time.perf_counter()
        proposal = await suggest_mapping(case.name, columns, llm)
        report.latencies_ms.append(int((time.perf_counter() - started) * 1000))
        if any("heuristics" in w for w in proposal.warnings):
            report.fallbacks += 1
        for actual in proposal.fields:
            report.results.append(score_field(case.name, case.expected[actual.target], actual))
    return report


async def evaluate_names(cases: list[NameCase], llm: LLMProvider) -> NameReport:
    started = time.perf_counter()
    outcome = await NameSplitter(llm, InMemoryCache()).split([c.input for c in cases])
    report = NameReport(llm_calls=outcome.stats.llm_calls)
    for case in cases:
        first = outcome.result(case.input, "first")
        last = outcome.result(case.input, "last")
        got_first = _text(first)
        got_last = _text(last)
        ok = (got_first, got_last) == (case.first, case.last)
        report.results.append(NameResult(case, got_first, got_last, ok))
    report.ms = int((time.perf_counter() - started) * 1000)
    return report


def _text(result: object) -> str:
    if isinstance(result, Ok):
        return result.value
    return "<error>"


def failures(
    mapping: MappingReport, names: NameReport, min_mapping: float, min_names: float
) -> list[str]:
    problems = []
    if mapping.full_accuracy < min_mapping:
        problems.append(f"mapping accuracy {mapping.full_accuracy:.1%} < {min_mapping:.0%}")
    if names.accuracy < min_names:
        problems.append(f"name split accuracy {names.accuracy:.1%} < {min_names:.0%}")
    return problems


def render_markdown(mapping: MappingReport, names: NameReport, model: str, when: str) -> str:
    average = 0
    if mapping.latencies_ms:
        average = sum(mapping.latencies_ms) // len(mapping.latencies_ms)
    lines = [
        f"# Eval report · {model} · {when}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Mapping: column + transform correct | {mapping.full_accuracy:.1%} |",
        f"| Mapping: column correct | {mapping.source_accuracy:.1%} |",
        f"| Files that fell back to heuristics | {mapping.fallbacks} / {mapping.cases} |",
        f"| Average time per proposal | {average / 1000:.1f} s |",
        f"| Name split exact match | {names.accuracy:.1%} ({len(names.results)} names) |",
        f"| Name split model calls / time | {names.llm_calls} / {names.ms / 1000:.1f} s |",
        "",
        "## Mapping accuracy by field",
        "",
        "| Field | Accuracy |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:.1%} |" for k, v in mapping.accuracy_by_field().items()]
    lines += ["", "## Mapping misses", ""]
    misses = [r for r in mapping.results if not r.full_ok]
    if not misses:
        lines.append("None.")
    for r in misses:
        got = f"{r.actual.source} · {r.actual.transform} {r.actual.params}"
        lines.append(
            f"- `{r.case}` {r.target}: expected {r.expected}, got {got} ({r.actual.origin})"
        )
    lines += ["", "## Name split misses", ""]
    wrong = [r for r in names.results if not r.ok]
    if not wrong:
        lines.append("None.")
    for name in wrong:
        lines.append(
            f"- {name.case.input!r}: expected {name.case.first!r} | {name.case.last!r}, "
            f"got {name.first!r} | {name.last!r}"
        )
    return "\n".join(lines) + "\n"
