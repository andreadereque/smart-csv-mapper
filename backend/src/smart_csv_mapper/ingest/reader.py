"""Turn uploaded bytes into headers and rows of text.

Everything is read as text on purpose: types are decided later, explicitly, by the
transforms. No pandas (ADR-002).
"""

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass

from charset_normalizer import from_bytes

from smart_csv_mapper.ingest.errors import IngestError

CANDIDATE_DELIMITERS = ",;\t|"
SNIFF_SAMPLE_CHARS = 8192


@dataclass(frozen=True)
class ParsedCsv:
    headers: list[str]
    rows: list[list[str]]
    encoding: str
    delimiter: str


def decode(raw: bytes) -> tuple[str, str]:
    """Return the text and the encoding used. UTF-8 first, then a best guess."""
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        pass
    best = from_bytes(raw).best()
    if best is None:
        raise IngestError("unreadable_encoding", "Could not detect the file encoding.")
    return str(best), best.encoding


def detect_delimiter(text: str) -> str:
    sample = text[:SNIFF_SAMPLE_CHARS]
    try:
        return csv.Sniffer().sniff(sample, delimiters=CANDIDATE_DELIMITERS).delimiter
    except csv.Error:
        pass
    first_line = sample.split("\n", 1)[0]
    counts = {d: first_line.count(d) for d in CANDIDATE_DELIMITERS}
    best = max(counts, key=lambda d: counts[d])
    if counts[best] == 0:
        return ","
    return best


def _check_headers(headers: list[str]) -> None:
    if any(h == "" for h in headers):
        raise IngestError("missing_header", "Every column needs a header name.")
    seen: set[str] = set()
    for header in headers:
        if header.lower() in seen:
            raise IngestError("duplicate_header", f"Duplicate column header: {header!r}.")
        seen.add(header.lower())


def _read_rows(reader: Iterable[list[str]], width: int, max_rows: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) > width:
            number = len(rows) + 1
            raise IngestError("row_too_long", f"Data row {number} has more cells than headers.")
        if len(rows) == max_rows:
            raise IngestError("too_many_rows", f"The file has more than {max_rows} rows.")
        rows.append(row + [""] * (width - len(row)))
    return rows


def parse_csv(raw: bytes, max_rows: int) -> ParsedCsv:
    text, encoding = decode(raw)
    if not text.strip():
        raise IngestError("empty_file", "The file is empty.")
    delimiter = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    try:
        headers = [h.strip() for h in next(reader)]
        _check_headers(headers)
        rows = _read_rows(reader, len(headers), max_rows)
    except csv.Error as error:
        raise IngestError("malformed_csv", f"The file is not valid CSV: {error}.") from None
    if not rows:
        raise IngestError("no_rows", "The file has headers but no data rows.")
    return ParsedCsv(headers=headers, rows=rows, encoding=encoding, delimiter=delimiter)
