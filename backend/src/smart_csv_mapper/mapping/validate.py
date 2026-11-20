"""Check the model's answer against reality: real columns, real transforms, right params."""

from smart_csv_mapper.ingest.profile import ColumnProfile
from smart_csv_mapper.mapping.models import FieldMapping, LLMMappingAnswer
from smart_csv_mapper.schema import FIELDS_BY_NAME
from smart_csv_mapper.transforms.catalog import LLM_TRANSFORMS, check_params


def validate_answer(
    answer: LLMMappingAnswer, columns: list[ColumnProfile]
) -> tuple[dict[str, FieldMapping], list[str]]:
    """Return the usable mappings by target, and the problems to send back to the model."""
    by_lower = {c.name.lower(): c.name for c in columns}
    accepted: dict[str, FieldMapping] = {}
    errors: list[str] = []
    for item in answer.mappings:
        if item.target not in FIELDS_BY_NAME:
            errors.append(f"unknown target field {item.target!r}")
            continue
        if item.target in accepted:
            errors.append(f"target {item.target!r} appears more than once")
            continue
        if item.source is None:
            continue
        source = by_lower.get(item.source.strip().lower())
        if source is None:
            errors.append(f"{item.target}: column {item.source!r} does not exist in the file")
            continue
        spec = LLM_TRANSFORMS.get(item.transform)
        if spec is None:
            errors.append(f"{item.target}: transform {item.transform!r} is not allowed")
            continue
        problem = check_params(spec, item.params)
        if problem is not None:
            errors.append(f"{item.target}: {problem}")
            continue
        accepted[item.target] = FieldMapping(
            target=item.target,
            source=source,
            transform=item.transform,
            params=item.params,
            confidence=item.confidence,
            origin="llm",
        )
    return accepted, errors
