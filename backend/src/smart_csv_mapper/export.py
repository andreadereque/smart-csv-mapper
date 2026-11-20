"""Write the clean rows as CSV, safe to open in a spreadsheet (no formula injection)."""

import csv
import io
import re

from smart_csv_mapper.schema import TARGET_SCHEMA

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
PLAIN_NUMBER = re.compile(r"^[+-]?\d[\d.]*$")


def neutralise(cell: str) -> str:
    """Prefix a quote so spreadsheets show the text instead of running it as a formula.

    '+' and '-' are kept when the cell is a plain number or an E.164 phone, which are
    legitimate and harmless; '=', '@', tab and CR are always neutralised (OWASP CSV injection).
    """
    if not cell.startswith(FORMULA_START):
        return cell
    if cell[0] in "+-" and PLAIN_NUMBER.match(cell):
        return cell
    return "'" + cell


def to_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    names = [f.name for f in TARGET_SCHEMA]
    writer.writerow(names)
    for row in rows:
        writer.writerow([neutralise(row[name]) for name in names])
    return buffer.getvalue()
