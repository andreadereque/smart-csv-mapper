"""The closed list of transforms. The LLM may only choose from this list (ADR-005, ADR-006)."""

from collections.abc import Callable
from dataclasses import dataclass, field

from smart_csv_mapper.transforms import functions
from smart_csv_mapper.transforms.result import Err, Result

TransformFn = Callable[[str, dict[str, str]], Result]


@dataclass(frozen=True)
class TransformSpec:
    name: str
    description: str
    fn: TransformFn
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    free_params: bool = field(default=False)  # map_values: any key is a lookup entry
    llm_allowed: bool = True  # False = only a person may choose it in the UI


CATALOG: dict[str, TransformSpec] = {
    spec.name: spec
    for spec in [
        TransformSpec("trim", "Remove leading and trailing spaces.", functions.trim),
        TransformSpec("lowercase_trim", "Trim and lowercase (emails).", functions.lowercase_trim),
        TransformSpec(
            "parse_eu_number",
            "European number like '1.250,50' or '80,00' → '1250.50'. Strips € $ £.",
            functions.parse_eu_number,
        ),
        TransformSpec(
            "parse_us_number",
            "US number like '1,250.50' → '1250.50'. Strips € $ £.",
            functions.parse_us_number,
        ),
        TransformSpec(
            "parse_date",
            "Date with an explicit strftime format, e.g. {'format': '%d/%m/%Y'} → ISO.",
            functions.parse_date,
            required_params=("format",),
        ),
        TransformSpec(
            "normalize_phone",
            "Phone to E.164 ('+34612345678'); numbers without prefix use default_country.",
            functions.normalize_phone,
            optional_params=("default_country",),
        ),
        TransformSpec(
            "constant",
            "Ignore the column and always use {'value': ...}.",
            functions.constant,
            required_params=("value",),
            llm_allowed=False,
        ),
        TransformSpec(
            "map_values",
            "Map each value through a lookup table, e.g. {'pagado': '0', '*': 'keep'}.",
            functions.map_values,
            free_params=True,
            llm_allowed=False,
        ),
    ]
}

LLM_TRANSFORMS = {name: spec for name, spec in CATALOG.items() if spec.llm_allowed}


def check_params(spec: TransformSpec, params: dict[str, str]) -> str | None:
    """Return an error message when the params don't fit the transform; None when they do."""
    missing = [p for p in spec.required_params if p not in params]
    if missing:
        return f"{spec.name} needs params: {', '.join(missing)}"
    if spec.free_params:
        return None
    allowed = set(spec.required_params) | set(spec.optional_params)
    unknown = sorted(set(params) - allowed)
    if unknown:
        return f"{spec.name} does not accept params: {', '.join(unknown)}"
    return None


def apply(name: str, value: str, params: dict[str, str]) -> Result:
    spec = CATALOG.get(name)
    if spec is None:
        return Err(f"unknown transform: {name!r}")
    problem = check_params(spec, params)
    if problem is not None:
        return Err(problem)
    return spec.fn(value, params)
