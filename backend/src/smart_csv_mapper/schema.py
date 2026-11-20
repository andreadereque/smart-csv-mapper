"""The fixed target schema (PLAN §4). Defined once; the API, the prompt and the UI read it."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from smart_csv_mapper.transforms.result import Err, Ok, Result

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def _text(value: str) -> Result:
    return Ok(value.strip())


def _email(value: str) -> Result:
    if not EMAIL.match(value):
        return Err(f"invalid email: {value!r}")
    return Ok(value)


def _phone(value: str) -> Result:
    if not E164.match(value):
        return Err(f"phone must be E.164 like +34612345678: {value!r}")
    return Ok(value)


def _amount(value: str) -> Result:
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return Err(f"amount must be a number: {value!r}")
    if not amount.is_finite() or amount < 0:
        return Err(f"amount must be zero or positive: {value!r}")
    return Ok(str(amount.quantize(Decimal("0.01"))))


def _date(value: str) -> Result:
    try:
        return Ok(date.fromisoformat(value).isoformat())
    except ValueError:
        return Err(f"date must be ISO 8601 (YYYY-MM-DD): {value!r}")


@dataclass(frozen=True)
class TargetField:
    name: str
    type: str
    required: bool
    description: str
    validate: Callable[[str], Result]


TARGET_SCHEMA: tuple[TargetField, ...] = (
    TargetField("external_id", "string", True, "The client's own id for the debtor.", _text),
    TargetField("first_name", "string", True, "Given name(s).", _text),
    TargetField("last_name", "string", True, "Family name(s).", _text),
    TargetField("email", "email", False, "Contact email.", _email),
    TargetField("phone", "phone", False, "Contact phone, E.164.", _phone),
    TargetField("amount_due", "decimal", True, "Amount owed, ≥ 0, two decimals.", _amount),
    TargetField("due_date", "date", False, "When the amount is due, ISO 8601.", _date),
)

FIELDS_BY_NAME = {f.name: f for f in TARGET_SCHEMA}


def validate_value(field_name: str, value: str) -> Result:
    """Final check of an already-transformed value. Empty is only an error if required."""
    target = FIELDS_BY_NAME[field_name]
    text = value.strip()
    if text == "":
        if target.required:
            return Err(f"{field_name} is required")
        return Ok("")
    return target.validate(text)
