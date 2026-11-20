import pytest
from conftest import fixture_bytes

from smart_csv_mapper.ingest.errors import IngestError
from smart_csv_mapper.ingest.reader import decode, detect_delimiter, parse_csv


def test_reads_utf8_with_comma_and_quoted_decimal() -> None:
    parsed = parse_csv(fixture_bytes("clientes_es.csv"), max_rows=100)
    assert parsed.headers == ["Nombre completo", "Correo", "Tlf", "Importe (€)"]
    assert parsed.rows[0] == ["María López García", "maria@example.com", "612 345 678", "1.250,50"]
    assert parsed.encoding == "utf-8"
    assert parsed.delimiter == ","


def test_reads_semicolon_and_keeps_empty_cells() -> None:
    parsed = parse_csv(fixture_bytes("semicolon.csv"), max_rows=100)
    assert parsed.delimiter == ";"
    assert parsed.rows[1] == ["Ana", "Ruiz", "", "12.5"]


def test_reads_latin1_tab_separated() -> None:
    parsed = parse_csv(fixture_bytes("latin1_tab.tsv"), max_rows=100)
    assert parsed.delimiter == "\t"
    assert parsed.encoding != "utf-8"
    assert parsed.rows[0][1] == "Zoë Müller"


def test_keeps_newlines_and_commas_inside_quotes_and_skips_blank_lines() -> None:
    parsed = parse_csv(fixture_bytes("quoted.csv"), max_rows=100)
    assert parsed.rows == [
        ["1", "line one\nline two", "5"],
        ["2", "has, a comma", "7"],
        ["3", "", ""],
    ]


def test_strips_utf8_bom_and_header_spaces() -> None:
    parsed = parse_csv("﻿ id , name \n1,Ana\n".encode(), max_rows=10)
    assert parsed.headers == ["id", "name"]


def test_pads_short_rows() -> None:
    parsed = parse_csv(b"a,b,c\n1,2\n", max_rows=10)
    assert parsed.rows == [["1", "2", ""]]


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"", "empty_file"),
        (b"  \n \n", "empty_file"),
        (b"a,b\n", "no_rows"),
        (b"a,,c\n1,2,3\n", "missing_header"),
        (b"Email,email\n1,2\n", "duplicate_header"),
        (b"email,Email\n1,2\n", "duplicate_header"),
        (b"a,b\n1,2,3\n", "row_too_long"),
    ],
)
def test_rejects_invalid_files_with_a_stable_code(raw: bytes, code: str) -> None:
    with pytest.raises(IngestError) as error:
        parse_csv(raw, max_rows=10)
    assert error.value.code == code


def test_rejects_more_rows_than_the_limit_but_accepts_exactly_the_limit() -> None:
    body = b"a\n" + b"x\n" * 3
    assert len(parse_csv(body, max_rows=3).rows) == 3
    with pytest.raises(IngestError) as error:
        parse_csv(body, max_rows=2)
    assert error.value.code == "too_many_rows"


def test_decode_fails_on_binary_garbage() -> None:
    with pytest.raises(IngestError) as error:
        decode(bytes(range(256)) * 4)
    assert error.value.code == "unreadable_encoding"


def test_detect_delimiter_falls_back_to_counting_when_sniffer_fails() -> None:
    assert detect_delimiter("a|b|c") == "|"


def test_detect_delimiter_defaults_to_comma_for_a_single_column() -> None:
    assert detect_delimiter("just one column") == ","


def test_skips_rows_that_only_contain_spaces() -> None:
    parsed = parse_csv(b"a,b\n  ,  \n1,2\n", max_rows=10)
    assert parsed.rows == [["1", "2"]]
