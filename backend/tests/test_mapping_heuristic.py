import pytest
from helpers import SPANISH_COLUMNS, column

from smart_csv_mapper.mapping.heuristic import (
    choose_transform,
    guess_date_format,
    heuristic_field,
    normalise_header,
    number_transform,
)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Importe (€)", "importe"),
        ("Correo Electrónico", "correo electronico"),
        ("  first_name ", "first name"),
        ("E-Mail", "e mail"),
    ],
)
def test_normalise_header(header: str, expected: str) -> None:
    assert normalise_header(header) == expected


def test_maps_spanish_headers_with_the_right_transforms() -> None:
    mapped = {
        t: heuristic_field(t, SPANISH_COLUMNS)
        for t in [
            "external_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "amount_due",
            "due_date",
        ]
    }
    assert {t: m.source for t, m in mapped.items()} == {
        "external_id": "Referencia",
        "first_name": "Nombre",
        "last_name": "Apellidos",
        "email": "Correo",
        "phone": "Tlf",
        "amount_due": "Importe (€)",
        "due_date": "Vencimiento",
    }
    assert mapped["email"].transform == "lowercase_trim"
    assert mapped["phone"].transform == "normalize_phone"
    assert mapped["amount_due"].transform == "parse_eu_number"
    assert (mapped["due_date"].transform, mapped["due_date"].params) == (
        "parse_date",
        {"format": "%d/%m/%Y"},
    )
    assert mapped["email"].origin == "heuristic"
    assert mapped["email"].confidence == 0.8


def test_fuzzy_match_has_lower_confidence_than_an_exact_synonym() -> None:
    mapped = heuristic_field("phone", [column("Telefon", "612 345 678")])
    assert mapped.source == "Telefon"
    assert mapped.confidence == 0.65


def test_unrelated_headers_stay_unmapped() -> None:
    mapped = heuristic_field("phone", [column("notes", "x"), column("colour", "red")])
    assert mapped.source is None
    assert mapped.origin == "none"
    assert mapped.confidence == 0


def test_picks_the_best_scoring_column() -> None:
    mapped = heuristic_field("phone", [column("Telefon", "x"), column("Tlf", "y")])
    assert mapped.source == "Tlf"


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        (["1.250,50", "80,00"], "parse_eu_number"),
        (["€ 12,5"], "parse_eu_number"),
        (["1,250.50", "980.00"], "parse_us_number"),
        (["$1,000"], "parse_us_number"),
        (["100", "250"], "parse_us_number"),
        (["1,250.50", "80,00"], "parse_eu_number"),
        (["n/a"], "parse_eu_number"),
        ([], "parse_eu_number"),
    ],
)
def test_number_format_detection(samples: list[str], expected: str) -> None:
    assert number_transform(samples) == expected


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        (["2026-11-20"], "%Y-%m-%d"),
        (["20/11/2026", "01/12/2026"], "%d/%m/%Y"),
        (["11/20/2026"], "%m/%d/%Y"),
        (["20.11.2026"], "%d.%m.%Y"),
        (["soon"], None),
    ],
)
def test_date_format_detection(samples: list[str], expected: str | None) -> None:
    assert guess_date_format(samples) == expected


def test_unrecognised_dates_fall_back_to_trim() -> None:
    assert choose_transform("due_date", column("Fecha", "next week")) == ("trim", {})


def test_text_fields_use_trim() -> None:
    assert choose_transform("first_name", column("Nombre", "Ana")) == ("trim", {})


@pytest.mark.parametrize(
    ("target", "header"),
    [
        ("amount_due", "Deuda pendiente"),
        ("due_date", "Fecha venc."),
        ("email", "contact_email"),
        ("external_id", "customer_ref"),
    ],
)
def test_a_synonym_as_a_whole_word_scores_between_exact_and_fuzzy(target: str, header: str) -> None:
    mapped = heuristic_field(target, [column(header, "x")])
    assert (mapped.source, mapped.confidence) == (header, 0.7)


def test_a_synonym_inside_another_word_does_not_count() -> None:
    assert heuristic_field("external_id", [column("Provider", "x")]).source is None


def test_a_full_name_column_feeds_first_and_last_name_with_split_transforms() -> None:
    columns = [column("Nombre completo", "María López García"), column("Correo", "a@b.com")]
    first = heuristic_field("first_name", columns)
    last = heuristic_field("last_name", columns)
    assert (first.source, first.transform) == ("Nombre completo", "split_name_first")
    assert (last.source, last.transform) == ("Nombre completo", "split_name_last")
    assert first.confidence == 0.8


def test_separate_name_columns_win_over_a_generic_name_column() -> None:
    columns = [column("Nombre", "Ana"), column("Apellidos", "Ruiz"), column("Cliente", "Acme SL")]
    assert heuristic_field("first_name", columns).transform == "trim"
    assert heuristic_field("last_name", columns).source == "Apellidos"


def test_no_columns_means_unmapped() -> None:
    assert heuristic_field("email", []).source is None


def test_columns_already_taken_are_not_reused() -> None:
    columns = [column("Amount Due", "100.00"), column("Notes", "x")]
    assert heuristic_field("due_date", columns).source == "Amount Due"
    assert heuristic_field("due_date", columns, frozenset({"Amount Due"})).source is None
