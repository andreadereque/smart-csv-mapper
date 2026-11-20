import json
from pathlib import Path

import pytest

from smart_csv_mapper.evaluation import (
    Expected,
    MappingCase,
    MappingReport,
    NameCase,
    NameReport,
    NameResult,
    evaluate_mapping,
    evaluate_names,
    failures,
    load_mapping_cases,
    load_name_cases,
    render_markdown,
    score_field,
)
from smart_csv_mapper.llm.base import LLMError
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.mapping.models import FieldMapping

CSV = b"Ref;Nombre;Correo;Importe;Vence\nR-1;Ana;a@example.com;1.250,50;20/11/2026\n"
EXPECTED: Expected = {
    "external_id": {"source": "Ref", "transform": "trim"},
    "first_name": {"source": "Nombre", "transform": "trim"},
    "last_name": {"source": None},
    "email": {"source": "Correo", "transform": "lowercase_trim"},
    "phone": {"source": None},
    "amount_due": {"source": "Importe", "transform": "parse_eu_number"},
    "due_date": {"source": "Vence", "transform": "parse_date", "params": {"format": "%d/%m/%Y"}},
}


def answer(**overrides: object) -> dict[str, object]:
    items = {
        "external_id": ("Ref", "trim", {}),
        "first_name": ("Nombre", "trim", {}),
        "last_name": (None, "trim", {}),
        "email": ("Correo", "lowercase_trim", {}),
        "phone": (None, "trim", {}),
        "amount_due": ("Importe", "parse_eu_number", {}),
        "due_date": ("Vence", "parse_date", {"format": "%d/%m/%Y"}),
    }
    items.update(overrides)  # type: ignore[arg-type]
    return {
        "mappings": [
            {"target": t, "source": s, "transform": tr, "params": p, "confidence": 0.9}
            for t, (s, tr, p) in items.items()
        ]
    }


def field(**kwargs: object) -> FieldMapping:
    return FieldMapping.model_validate({"target": "due_date", "origin": "llm", **kwargs})


@pytest.mark.parametrize(
    ("actual", "source_ok", "full_ok"),
    [
        (field(source="Vence", transform="parse_date", params={"format": "%d/%m/%Y"}), True, True),
        (field(source="Vence", transform="parse_date", params={"format": "%m/%d/%Y"}), True, False),
        (field(source="Vence", transform="trim"), True, False),
        (
            field(source="Other", transform="parse_date", params={"format": "%d/%m/%Y"}),
            False,
            False,
        ),
    ],
)
def test_score_field(actual: FieldMapping, source_ok: bool, full_ok: bool) -> None:
    result = score_field("c", EXPECTED["due_date"], actual)
    assert (result.source_ok, result.full_ok) == (source_ok, full_ok)


def test_an_expected_empty_field_is_right_only_when_left_empty() -> None:
    assert score_field("c", {"source": None}, field()).full_ok is True
    assert score_field("c", {"source": None}, field(source="Vence")).full_ok is False


def test_extra_params_that_were_not_expected_do_not_count_against() -> None:
    actual = field(
        target="phone", source="Tlf", transform="normalize_phone", params={"default_country": "ES"}
    )
    expected: dict[str, object] = {"source": "Tlf", "transform": "normalize_phone"}
    assert score_field("c", expected, actual).full_ok is True


async def test_evaluate_mapping_scores_every_field_and_counts_fallbacks() -> None:
    cases = [MappingCase("good", CSV, EXPECTED), MappingCase("down", CSV, EXPECTED)]
    # The labels say US format; the model's EU choice passes its own checks but is scored wrong.
    expected_us: Expected = {
        **EXPECTED,
        "amount_due": {"source": "Importe", "transform": "parse_us_number"},
    }
    cases = [MappingCase("good", CSV, expected_us), MappingCase("down", CSV, expected_us)]
    llm = FakeProvider([answer(), LLMError("timeout", "slow")])
    report = await evaluate_mapping(cases, llm)
    assert report.cases == 2
    assert len(report.results) == 14
    assert len(report.latencies_ms) == 2
    assert report.fallbacks == 1
    by_case = {(r.case, r.target): r for r in report.results}
    assert by_case[("good", "amount_due")].full_ok is False
    assert by_case[("good", "amount_due")].source_ok is True
    assert by_case[("good", "due_date")].full_ok is True
    assert report.accuracy_by_field()["email"] == 1.0
    assert report.accuracy_by_field()["amount_due"] < 1.0


async def test_evaluate_names_requires_an_exact_match() -> None:
    cases = [
        NameCase("Ana Ruiz", "Ana", "Ruiz"),
        NameCase("maría gil", "maría", "gil"),
        NameCase("Luis Gil", "Luis", "Gil"),
    ]
    llm = FakeProvider(
        [
            {
                "results": [
                    {"input": "Ana Ruiz", "first_name": "Ana", "last_name": "Ruiz"},
                    {"input": "maría gil", "first_name": "María", "last_name": "gil"},
                    {"input": "Luis Gil", "first_name": "Lu", "last_name": "Gil"},
                ]
            },
            {"results": [{"input": "Luis Gil", "first_name": "Lu", "last_name": "Gil"}]},
        ]
    )
    report = await evaluate_names(cases, llm)
    assert [r.ok for r in report.results] == [True, False, False]
    assert report.results[1].first == "<error>"  # recased by the model → rejected, never "María"
    assert report.results[2].first == "<error>"
    assert report.accuracy == pytest.approx(1 / 3, abs=1e-3)
    assert report.llm_calls == 2


def test_the_threshold_uses_column_and_transform_not_just_column() -> None:
    wrong_transform = score_field("c", EXPECTED["email"], field(target="email", source="Correo"))
    mapping = MappingReport(results=[wrong_transform])
    names = NameReport(results=[NameResult(NameCase("A B", "A", "B"), "A", "B", True)])
    assert mapping.source_accuracy == 1.0
    assert failures(mapping, names, 0.5, 0.5) == ["mapping accuracy 0.0% < 50%"]


def test_failures_compares_against_both_thresholds() -> None:
    mapping = MappingReport()
    names = NameReport()
    assert failures(mapping, names, 0.0, 0.0) == []
    assert failures(mapping, names, 0.85, 0.9) == [
        "mapping accuracy 0.0% < 85%",
        "name split accuracy 0.0% < 90%",
    ]


async def test_report_lists_metrics_and_misses() -> None:
    expected_us: Expected = {
        **EXPECTED,
        "amount_due": {"source": "Importe", "transform": "parse_us_number"},
    }
    mapping = await evaluate_mapping(
        [MappingCase("good", CSV, expected_us)], FakeProvider([answer()])
    )
    names = await evaluate_names(
        [NameCase("Ana Ruiz", "Ana", "Ruiz")],
        FakeProvider(
            [{"results": [{"input": "Ana Ruiz", "first_name": "Ana", "last_name": "Ruiz"}]}]
        ),
    )
    text = render_markdown(mapping, names, "qwen2.5:3b", "2026-11-20")
    assert text.startswith("# Eval report · qwen2.5:3b · 2026-11-20")
    assert "| Mapping: column + transform correct | 85.7% |" in text
    assert "| Mapping: column correct | 100.0% |" in text
    assert "| amount_due | 0.0% |" in text
    assert "- `good` amount_due: expected" in text
    assert "got Importe · parse_eu_number {} (llm)" in text
    assert "## Name split misses\n\nNone." in text


def test_report_with_no_runs_and_name_misses() -> None:
    names = NameReport()
    names.results.append(
        NameResult(NameCase("Ana Ruiz", "Ana", "Ruiz"), "<error>", "<error>", False)
    )
    text = render_markdown(MappingReport(), names, "m", "d")
    assert "| Average time per proposal | 0.0 s |" in text
    assert "## Mapping misses\n\nNone." in text
    assert "- 'Ana Ruiz': expected 'Ana' | 'Ruiz', got '<error>' | '<error>'" in text


def test_loaders_read_the_datasets(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(CSV)
    (tmp_path / "a.expected.json").write_text(json.dumps(EXPECTED), encoding="utf-8")
    [case] = load_mapping_cases(tmp_path)
    assert (case.name, case.raw, case.expected) == ("a", CSV, EXPECTED)
    names = tmp_path / "names.jsonl"
    names.write_text('{"input": "Ana Ruiz", "first": "Ana", "last": "Ruiz"}\n\n', encoding="utf-8")
    assert load_name_cases(names) == [NameCase("Ana Ruiz", "Ana", "Ruiz")]


def test_the_real_datasets_are_well_formed() -> None:
    root = Path(__file__).parents[2] / "evals"
    cases = load_mapping_cases(root / "datasets")
    assert len(cases) == 15
    for case in cases:
        assert set(case.expected) == {
            "external_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "amount_due",
            "due_date",
        }
    assert len(load_name_cases(root / "name_split.jsonl")) == 60
