"""Fallback mapping without a model: header synonyms + fuzzy match + sample-based transform.

Used when the model is down or keeps answering badly, and to fill fields the model left empty.
"""

import difflib
import re
import unicodedata
from datetime import datetime

from smart_csv_mapper.ingest.profile import ColumnProfile
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.transforms.functions import US_NUMBER

SYNONYMS: dict[str, tuple[str, ...]] = {
    "external_id": (
        "id",
        "external id",
        "client id",
        "customer id",
        "ref",
        "reference",
        "referencia",
        "codigo",
        "code",
        "id cliente",
    ),
    "first_name": ("first name", "first", "firstname", "given name", "forename", "nombre"),
    "last_name": ("last name", "surname", "lastname", "family name", "apellido", "apellidos"),
    "email": ("email", "e mail", "mail", "correo", "correo electronico", "email address"),
    "phone": ("phone", "telephone", "tel", "tlf", "telefono", "movil", "mobile", "phone number"),
    "amount_due": (
        "amount",
        "amount due",
        "debt",
        "deuda",
        "importe",
        "saldo",
        "balance",
        "total",
        "importe pendiente",
    ),
    "due_date": ("due date", "due", "fecha", "vencimiento", "fecha vencimiento", "date"),
}
FULL_NAME = (
    "full name",
    "name",
    "nombre completo",
    "nombre y apellidos",
    "customer name",
    "client name",
    "cliente",
    "titular",
    "deudor",
    "debtor",
)
SPLIT_TRANSFORMS = {"first_name": "split_name_first", "last_name": "split_name_last"}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y")
EXACT_CONFIDENCE = 0.8
WORD_CONFIDENCE = 0.7
FUZZY_THRESHOLD = 0.85


def normalise_header(header: str) -> str:
    text = re.sub(r"\(.*?\)", " ", header)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _score(synonyms: tuple[str, ...], header: str) -> float:
    name = normalise_header(header)
    if name in synonyms:
        return EXACT_CONFIDENCE
    words = set(name.split())
    if any(" " not in s and s in words for s in synonyms):
        return WORD_CONFIDENCE
    best = max(difflib.SequenceMatcher(None, name, s).ratio() for s in synonyms)
    if best >= FUZZY_THRESHOLD:
        return round(best * 0.7, 2)
    return 0.0


def guess_date_format(samples: list[str]) -> str | None:
    for fmt in DATE_FORMATS:
        try:
            for sample in samples:
                datetime.strptime(sample.strip(), fmt)
        except ValueError:
            continue
        return fmt
    return None


def number_transform(samples: list[str]) -> str:
    """US format only when every sample reads as US; plain integers read the same either way."""
    cleaned = [re.sub(r"[\s€$£]", "", s) for s in samples]
    if cleaned and all(US_NUMBER.match(s) for s in cleaned):
        return "parse_us_number"
    return "parse_eu_number"


def choose_transform(target: str, column: ColumnProfile) -> tuple[str, dict[str, str]]:
    if target == "email":
        return "lowercase_trim", {}
    if target == "phone":
        return "normalize_phone", {}
    if target == "amount_due":
        return number_transform(column.samples), {}
    if target == "due_date":
        fmt = guess_date_format(column.samples)
        if fmt is not None:
            return "parse_date", {"format": fmt}
    return "trim", {}


def _best(synonyms: tuple[str, ...], columns: list[ColumnProfile]) -> tuple[float, ColumnProfile]:
    scored = [(_score(synonyms, c.name), c) for c in columns]
    return max(scored, key=lambda pair: pair[0])


def heuristic_field(target: str, columns: list[ColumnProfile]) -> FieldMapping:
    if not columns:
        return FieldMapping(target=target)
    score, column = _best(SYNONYMS[target], columns)
    if target in SPLIT_TRANSFORMS:
        full_score, full_column = _best(FULL_NAME, columns)
        if full_score > score:
            return FieldMapping(
                target=target,
                source=full_column.name,
                transform=SPLIT_TRANSFORMS[target],
                confidence=full_score,
                origin="heuristic",
            )
    if score == 0:
        return FieldMapping(target=target)
    transform, params = choose_transform(target, column)
    return FieldMapping(
        target=target,
        source=column.name,
        transform=transform,
        params=params,
        confidence=score,
        origin="heuristic",
    )
