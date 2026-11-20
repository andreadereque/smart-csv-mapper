import pytest
from helpers import SPANISH_COLUMNS, column, good_answer

from smart_csv_mapper.mapping.models import LLMMappingAnswer
from smart_csv_mapper.mapping.validate import looks_like_full_names, validate_answer


def _answer(*items: dict[str, object]) -> LLMMappingAnswer:
    return LLMMappingAnswer.model_validate({"mappings": list(items)})


def _item(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": "email",
        "source": "Correo",
        "transform": "lowercase_trim",
        "params": {},
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def test_a_good_answer_is_accepted_and_column_case_is_fixed() -> None:
    accepted, errors = validate_answer(
        LLMMappingAnswer.model_validate(good_answer()), SPANISH_COLUMNS
    )
    assert errors == []
    assert len(accepted) == 7
    assert accepted["email"].source == "Correo"
    assert accepted["email"].origin == "llm"
    assert accepted["due_date"].params == {"format": "%d/%m/%Y"}


def test_null_source_is_not_an_error_but_is_not_accepted() -> None:
    accepted, errors = validate_answer(_answer(_item(source=None)), SPANISH_COLUMNS)
    assert (accepted, errors) == ({}, [])


def test_each_problem_is_reported_for_the_retry() -> None:
    accepted, errors = validate_answer(
        _answer(
            _item(target="colour"),
            _item(source="Mail"),
            _item(target="phone", source="Tlf", transform="to_phone"),
            _item(target="due_date", source="Vencimiento", transform="parse_date"),
            _item(target="first_name", source="Nombre", transform="trim"),
            _item(target="first_name", source="Apellidos", transform="trim"),
        ),
        SPANISH_COLUMNS,
    )
    assert list(accepted) == ["first_name"]
    assert accepted["first_name"].source == "Nombre"
    assert errors == [
        "unknown target field 'colour'",
        "email: column 'Mail' does not exist in the file",
        "phone: transform 'to_phone' is not allowed",
        "due_date: parse_date needs params: format",
        "target 'first_name' appears more than once",
    ]


def test_user_only_transforms_are_rejected_from_the_model() -> None:
    accepted, errors = validate_answer(
        _answer(
            _item(
                target="external_id",
                source="Referencia",
                transform="constant",
                params={"value": "C-001"},
            )
        ),
        SPANISH_COLUMNS,
    )
    assert accepted == {}
    assert errors == ["external_id: transform 'constant' is not allowed"]


def test_a_transform_that_does_not_fit_the_field_type_is_rejected() -> None:
    accepted, errors = validate_answer(
        _answer(_item(target="external_id", source="Referencia", transform="lowercase_trim")),
        SPANISH_COLUMNS,
    )
    assert accepted == {}
    assert errors == ["external_id: lowercase_trim does not fit a string field; use trim"]


def test_a_transform_that_fails_on_most_samples_is_rejected() -> None:
    accepted, errors = validate_answer(
        _answer(_item(target="amount_due", source="Importe (€)", transform="parse_us_number")),
        SPANISH_COLUMNS,
    )
    assert accepted == {}
    assert errors == [
        "amount_due: parse_us_number fails on the samples: "
        "'1.250,50' (not a US-format number: '1.250,50'); '80,00' (not a US-format number: '80,00')"
    ]


def test_a_wrong_date_format_is_caught_by_the_field_validation_too() -> None:
    _, errors = validate_answer(
        _answer(
            _item(
                target="due_date",
                source="Vencimiento",
                transform="parse_date",
                params={"format": "%m/%d/%Y"},
            )
        ),
        SPANISH_COLUMNS,
    )
    assert errors[0].startswith("due_date: parse_date fails on the samples: '20/11/2026'")


def test_one_bad_sample_out_of_three_is_tolerated() -> None:
    columns = [column("Importe", "1.250,50", "80,00", "n/a")]
    accepted, errors = validate_answer(
        _answer(_item(target="amount_due", source="Importe", transform="parse_eu_number")), columns
    )
    assert errors == []
    assert "amount_due" in accepted


def test_splitting_a_column_of_single_names_is_rejected() -> None:
    _, errors = validate_answer(
        _answer(_item(target="first_name", source="Nombre", transform="split_name_first")),
        SPANISH_COLUMNS,
    )
    assert errors == [
        "first_name: column 'Nombre' holds single names (e.g. 'María'), not full names; use trim"
    ]


def test_splitting_a_full_name_column_is_accepted() -> None:
    columns = [column("Cliente", "María López", "Gil, Pedro", "Ana")]
    accepted, errors = validate_answer(
        _answer(_item(target="last_name", source="Cliente", transform="split_name_last")), columns
    )
    assert errors == []
    assert accepted["last_name"].transform == "split_name_last"


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        (["María López", "Ana Gil"], True),
        (["López, María", "Ana"], True),
        (["López,María", "Gil,Ana"], True),
        (["María", "Ana", "Luis Gil"], False),
        ([], False),
    ],
)
def test_looks_like_full_names(samples: list[str], expected: bool) -> None:
    assert looks_like_full_names(samples) is expected


def test_a_column_whose_values_do_not_fit_the_field_is_rejected() -> None:
    _, errors = validate_answer(
        _answer(_item(target="email", source="Nombre", transform="lowercase_trim")),
        SPANISH_COLUMNS,
    )
    assert errors == [
        "email: lowercase_trim fails on the samples: 'María' (invalid email: 'maría'); "
        "'José' (invalid email: 'josé')"
    ]
