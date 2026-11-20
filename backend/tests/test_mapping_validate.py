from helpers import SPANISH_COLUMNS, good_answer

from smart_csv_mapper.mapping.models import LLMMappingAnswer
from smart_csv_mapper.mapping.validate import validate_answer


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
