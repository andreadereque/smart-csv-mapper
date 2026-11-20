"""Deterministic transforms: pure functions, same input → same output, always.

Every function receives the raw cell text and its params, and returns Ok or Err.
An empty cell stays empty: whether a field may be empty is the schema's decision.
"""

import re
from datetime import datetime
from decimal import Decimal

from smart_csv_mapper.transforms.result import Err, Ok, Result

CURRENCY_AND_SPACES = re.compile(r"[\s€$£]")
EU_NUMBER = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")
US_NUMBER = re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")
PHONE_NOISE = re.compile(r"[\s\-().]")
E164 = re.compile(r"^\+[1-9]\d{7,14}$")
COUNTRY_CODES = {"ES": "34", "GB": "44", "US": "1", "FR": "33", "DE": "49", "IT": "39", "PT": "351"}


def trim(value: str, params: dict[str, str]) -> Result:
    return Ok(value.strip())


def lowercase_trim(value: str, params: dict[str, str]) -> Result:
    return Ok(value.strip().lower())


def _to_decimal_text(text: str) -> Result:
    # The regexes above only let well-formed numbers through, so Decimal() cannot fail here.
    return Ok(str(Decimal(text)))


def parse_eu_number(value: str, params: dict[str, str]) -> Result:
    """'1.250,50' → '1250.50'."""
    text = CURRENCY_AND_SPACES.sub("", value)
    if text == "":
        return Ok("")
    if not EU_NUMBER.match(text):
        return Err(f"not a European-format number: {value!r}")
    return _to_decimal_text(text.replace(".", "").replace(",", "."))


def parse_us_number(value: str, params: dict[str, str]) -> Result:
    """'1,250.50' → '1250.50'."""
    text = CURRENCY_AND_SPACES.sub("", value)
    if text == "":
        return Ok("")
    if not US_NUMBER.match(text):
        return Err(f"not a US-format number: {value!r}")
    return _to_decimal_text(text.replace(",", ""))


def parse_date(value: str, params: dict[str, str]) -> Result:
    """Parse with an explicit strftime format (e.g. '%d/%m/%Y') → ISO 8601."""
    text = value.strip()
    if text == "":
        return Ok("")
    try:
        return Ok(datetime.strptime(text, params["format"]).date().isoformat())
    except ValueError:
        return Err(f"date {value!r} does not match format {params['format']!r}")


def normalize_phone(value: str, params: dict[str, str]) -> Result:
    """'612 345 678' → '+34612345678' (E.164). Numbers without a prefix get the default country."""
    text = PHONE_NOISE.sub("", value)
    if text == "":
        return Ok("")
    if text.startswith("00"):
        text = "+" + text[2:]
    if not text.startswith("+"):
        country = params.get("default_country", "ES").upper()
        if country not in COUNTRY_CODES:
            return Err(f"unknown country code: {country!r}")
        text = "+" + COUNTRY_CODES[country] + text.lstrip("0")
    if not E164.match(text):
        return Err(f"not a valid phone number: {value!r}")
    return Ok(text)


def constant(value: str, params: dict[str, str]) -> Result:
    """Ignore the cell and always return params['value']."""
    return Ok(params["value"])


def map_values(value: str, params: dict[str, str]) -> Result:
    """Look the cell up in params (case-insensitive). '*' is the fallback for anything else."""
    lookup = {k.strip().lower(): v for k, v in params.items()}
    key = value.strip().lower()
    if key in lookup:
        return Ok(lookup[key])
    if "*" in lookup:
        return Ok(lookup["*"])
    return Err(f"no mapping for value {value!r}")
