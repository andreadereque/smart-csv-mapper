import pytest

from smart_csv_mapper.export import neutralise, to_csv


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("=SUM(A1:A2)", "'=SUM(A1:A2)"),
        ("@cmd", "'@cmd"),
        ("+1+cmd|' /C calc'!A0", "'+1+cmd|' /C calc'!A0"),
        ("-2+3", "'-2+3"),
        ("\tTAB", "'\tTAB"),
        ("\rCR", "'\rCR"),
        ("+34612345678", "+34612345678"),
        ("-12.50", "-12.50"),
        ("Ana", "Ana"),
        ("", ""),
    ],
)
def test_formula_like_cells_are_neutralised_but_numbers_and_phones_are_kept(
    cell: str, expected: str
) -> None:
    assert neutralise(cell) == expected


def test_csv_has_the_schema_header_and_neutralised_cells() -> None:
    row = {
        "external_id": "=HYPERLINK(1)",
        "first_name": "Ana",
        "last_name": "Ruiz, Gil",
        "email": "",
        "phone": "+34612345678",
        "amount_due": "10.00",
        "due_date": "",
    }
    assert to_csv([row]) == (
        "external_id,first_name,last_name,email,phone,amount_due,due_date\n"
        '\'=HYPERLINK(1),Ana,"Ruiz, Gil",,+34612345678,10.00,\n'
    )
