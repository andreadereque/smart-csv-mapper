from smart_csv_mapper.cache import InMemoryCache
from smart_csv_mapper.ingest.reader import ParsedCsv
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.pipeline import Pipeline, check_mapping

HEADERS = ["Ref", "Nombre completo", "Correo", "Tlf", "Importe", "Vence"]
ROWS = [
    ["C-1", "Ana Ruiz", "ANA@EXAMPLE.COM", "612 345 678", "1.250,50", "20/11/2026"],
    ["C-2", "Luis Gil", "not-an-email", "", "80,00", ""],
    ["C-1", "Ana Ruiz", "", "", "-5,00", "31/02/2026"],
]
PARSED = ParsedCsv(headers=HEADERS, rows=ROWS, encoding="utf-8", delimiter=",")


def mapping(**overrides: FieldMapping) -> list[FieldMapping]:
    fields = {
        "external_id": FieldMapping(target="external_id", source="Ref"),
        "first_name": FieldMapping(
            target="first_name", source="Nombre completo", transform="split_name_first"
        ),
        "last_name": FieldMapping(
            target="last_name", source="Nombre completo", transform="split_name_last"
        ),
        "email": FieldMapping(target="email", source="Correo", transform="lowercase_trim"),
        "phone": FieldMapping(target="phone", source="Tlf", transform="normalize_phone"),
        "amount_due": FieldMapping(
            target="amount_due", source="Importe", transform="parse_eu_number"
        ),
        "due_date": FieldMapping(
            target="due_date", source="Vence", transform="parse_date", params={"format": "%d/%m/%Y"}
        ),
    }
    fields.update(overrides)
    return list(fields.values())


def splitter_answer() -> dict[str, object]:
    return {
        "results": [
            {"input": "Ana Ruiz", "first_name": "Ana", "last_name": "Ruiz"},
            {"input": "Luis Gil", "first_name": "Luis", "last_name": "Gil"},
        ]
    }


async def test_rows_are_transformed_validated_and_errors_point_to_the_cell() -> None:
    llm = FakeProvider([splitter_answer()])
    out = await Pipeline(llm, InMemoryCache()).run(PARSED, mapping())
    assert out.rows[0] == {
        "external_id": "C-1",
        "first_name": "Ana",
        "last_name": "Ruiz",
        "email": "ana@example.com",
        "phone": "+34612345678",
        "amount_due": "1250.50",
        "due_date": "2026-11-20",
    }
    assert out.rows[1]["email"] == ""
    problems = {(e.row, e.field): e.reason for e in out.errors}
    assert problems[(2, "email")] == "invalid email: 'not-an-email'"
    assert "zero or positive" in problems[(3, "amount_due")]
    assert "does not match format" in problems[(3, "due_date")]
    assert problems[(3, "external_id")] == "duplicate external_id (first seen in row 1)"
    assert (2, "phone") not in problems
    assert out.invalid_rows() == {2, 3}


async def test_one_split_per_source_column_shared_by_first_and_last_name() -> None:
    llm = FakeProvider([splitter_answer()])
    out = await Pipeline(llm, InMemoryCache()).run(PARSED, mapping())
    assert len(llm.prompts) == 1
    assert len(out.ai_stats) == 1
    stats = out.ai_stats[0]
    assert (stats.transform, stats.source, stats.rows, stats.distinct, stats.llm_calls) == (
        "split_name",
        "Nombre completo",
        3,
        2,
        1,
    )


async def test_unmapped_fields_are_empty_and_required_ones_are_errors() -> None:
    fields = mapping(
        email=FieldMapping(target="email"), external_id=FieldMapping(target="external_id")
    )
    out = await Pipeline(FakeProvider([splitter_answer()]), InMemoryCache()).run(PARSED, fields)
    assert out.rows[0]["email"] == ""
    assert [e.reason for e in out.errors if e.field == "external_id"] == [
        "external_id is required"
    ] * 3


async def test_limit_only_processes_the_first_rows() -> None:
    llm = FakeProvider(
        [{"results": [{"input": "Ana Ruiz", "first_name": "Ana", "last_name": "Ruiz"}]}]
    )
    out = await Pipeline(llm, InMemoryCache()).run(PARSED, mapping(), limit=1)
    assert len(out.rows) == 1
    assert '["Ana Ruiz"]' in llm.prompts[0]
    assert out.errors == []


async def test_split_transform_without_a_source_column_is_just_empty() -> None:
    fields = mapping(first_name=FieldMapping(target="first_name", transform="split_name_first"))
    out = await Pipeline(FakeProvider([splitter_answer()]), InMemoryCache()).run(PARSED, fields)
    assert [e.reason for e in out.errors if e.field == "first_name"] == [
        "AI transforms run on the whole column (distinct values, cached), not per cell"
    ] * 3


def test_check_mapping_reports_every_problem() -> None:
    fields = mapping(
        email=FieldMapping(target="email", source="Mail"),
        phone=FieldMapping(target="phone", source="Tlf", transform="to_phone"),
        due_date=FieldMapping(target="due_date", source="Vence", transform="parse_date"),
    )
    fields = [f for f in fields if f.target != "amount_due"]
    fields.append(FieldMapping(target="colour"))
    assert check_mapping(fields, HEADERS) == [
        "amount_due: missing from the mapping",
        "email: column 'Mail' does not exist",
        "phone: unknown transform 'to_phone'",
        "due_date: parse_date needs params: format",
        "unknown target field 'colour'",
    ]


def test_check_mapping_accepts_user_only_transforms() -> None:
    fields = mapping(
        external_id=FieldMapping(target="external_id", transform="constant", params={"value": "X"})
    )
    assert check_mapping(fields, HEADERS) == []
