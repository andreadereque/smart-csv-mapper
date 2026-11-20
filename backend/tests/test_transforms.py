from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from smart_csv_mapper.transforms.catalog import CATALOG, apply, check_params
from smart_csv_mapper.transforms.result import Err, Ok


@pytest.mark.parametrize(
    ("name", "raw", "params", "expected"),
    [
        ("trim", "  Ana  ", {}, "Ana"),
        ("lowercase_trim", " JOHN@EXAMPLE.COM ", {}, "john@example.com"),
        ("parse_eu_number", "1.250,50", {}, "1250.50"),
        ("parse_eu_number", "80,00 €", {}, "80.00"),
        ("parse_eu_number", "1.234.567", {}, "1234567"),
        ("parse_eu_number", "-12,5", {}, "-12.5"),
        ("parse_eu_number", "  ", {}, ""),
        ("parse_us_number", "$1,250.50", {}, "1250.50"),
        ("parse_us_number", "980.00", {}, "980.00"),
        ("parse_us_number", "", {}, ""),
        ("parse_date", "20/11/2026", {"format": "%d/%m/%Y"}, "2026-11-20"),
        ("parse_date", "11-20-26", {"format": "%m-%d-%y"}, "2026-11-20"),
        ("parse_date", " ", {"format": "%d/%m/%Y"}, ""),
        ("normalize_phone", "612 345 678", {}, "+34612345678"),
        ("normalize_phone", "+44 7700 900123", {}, "+447700900123"),
        ("normalize_phone", "0044 (7700) 900-123", {}, "+447700900123"),
        ("normalize_phone", "07700 900123", {"default_country": "gb"}, "+447700900123"),
        ("normalize_phone", "", {}, ""),
        ("constant", "whatever", {"value": "EUR"}, "EUR"),
        ("map_values", " Pagado ", {"pagado": "0", "pendiente": "1"}, "0"),
        ("map_values", "otro", {"pagado": "0", "*": "1"}, "1"),
    ],
)
def test_transform_happy_paths(name: str, raw: str, params: dict[str, str], expected: str) -> None:
    assert apply(name, raw, params) == Ok(expected)


@pytest.mark.parametrize(
    ("name", "raw", "params", "reason_part"),
    [
        ("parse_eu_number", "1,250.50", {}, "European"),
        ("parse_eu_number", "12.34", {}, "European"),
        ("parse_eu_number", "abc", {}, "European"),
        ("parse_us_number", "1.250,50", {}, "US-format"),
        ("parse_date", "31/02/2026", {"format": "%d/%m/%Y"}, "does not match"),
        ("parse_date", "2026-11-20", {"format": "%d/%m/%Y"}, "does not match"),
        ("normalize_phone", "12", {}, "not a valid phone"),
        ("normalize_phone", "+0034612", {}, "not a valid phone"),
        ("normalize_phone", "612345678", {"default_country": "XX"}, "unknown country"),
        ("map_values", "otro", {"pagado": "0"}, "no mapping"),
        ("nope", "x", {}, "unknown transform"),
        ("parse_date", "20/11/2026", {}, "needs params: format"),
        ("trim", "x", {"format": "%d"}, "does not accept params: format"),
    ],
)
def test_transform_errors_explain_why(
    name: str, raw: str, params: dict[str, str], reason_part: str
) -> None:
    result = apply(name, raw, params)
    assert isinstance(result, Err)
    assert reason_part in result.reason


def test_map_values_accepts_any_param_name() -> None:
    assert check_params(CATALOG["map_values"], {"anything": "x"}) is None


def test_optional_params_are_accepted() -> None:
    assert check_params(CATALOG["normalize_phone"], {"default_country": "ES"}) is None


@given(st.decimals(min_value=-(10**9), max_value=10**9, places=2, allow_nan=False))
def test_eu_and_us_formats_round_trip_to_the_same_number(number: Decimal) -> None:
    sign = ""
    if number < 0:
        sign = "-"
    integer, decimals = f"{abs(number):,.2f}".split(".")
    us = f"{sign}{integer}.{decimals}"
    eu = f"{sign}{integer.replace(',', '.')},{decimals}"
    us_result = apply("parse_us_number", us, {})
    eu_result = apply("parse_eu_number", eu, {})
    assert us_result == eu_result
    assert isinstance(us_result, Ok)
    assert Decimal(us_result.value) == number


@given(st.text())
def test_transforms_never_raise(text: str) -> None:
    for name, params in [
        ("parse_eu_number", {}),
        ("parse_us_number", {}),
        ("normalize_phone", {}),
        ("parse_date", {"format": "%d/%m/%Y"}),
        ("map_values", {"a": "b"}),
    ]:
        assert isinstance(apply(name, text, params), Ok | Err)


def test_ai_transforms_refuse_to_run_on_a_single_cell() -> None:
    result = apply("split_name_first", "Ana Ruiz", {})
    assert isinstance(result, Err)
    assert "whole column" in result.reason
