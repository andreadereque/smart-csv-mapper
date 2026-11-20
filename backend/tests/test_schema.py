import pytest

from smart_csv_mapper.schema import TARGET_SCHEMA, validate_value
from smart_csv_mapper.transforms.result import Err, Ok


def test_schema_has_the_planned_fields_in_order() -> None:
    assert [f.name for f in TARGET_SCHEMA] == [
        "external_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "amount_due",
        "due_date",
    ]
    assert [f.name for f in TARGET_SCHEMA if f.required] == [
        "external_id",
        "first_name",
        "last_name",
        "amount_due",
    ]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("first_name", "  Ana ", "Ana"),
        ("email", "ana@example.com", "ana@example.com"),
        ("phone", "+34612345678", "+34612345678"),
        ("amount_due", "1250.5", "1250.50"),
        ("amount_due", "0", "0.00"),
        ("due_date", "2026-11-20", "2026-11-20"),
        ("email", "", ""),
        ("phone", "   ", ""),
    ],
)
def test_valid_values_are_normalised(field: str, value: str, expected: str) -> None:
    assert validate_value(field, value) == Ok(expected)


@pytest.mark.parametrize(
    ("field", "value", "reason_part"),
    [
        ("first_name", "", "required"),
        ("amount_due", "  ", "required"),
        ("email", "not-an-email", "invalid email"),
        ("email", "a@b", "invalid email"),
        ("phone", "612345678", "E.164"),
        ("amount_due", "-0.01", "zero or positive"),
        ("amount_due", "Infinity", "zero or positive"),
        ("amount_due", "1.250,50", "must be a number"),
        ("due_date", "20/11/2026", "ISO 8601"),
    ],
)
def test_invalid_values_explain_why(field: str, value: str, reason_part: str) -> None:
    result = validate_value(field, value)
    assert isinstance(result, Err)
    assert reason_part in result.reason
