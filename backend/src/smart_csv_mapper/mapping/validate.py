"""Check the model's answer against reality: real columns, real transforms, right params."""

from smart_csv_mapper.ingest.profile import ColumnProfile
from smart_csv_mapper.mapping.models import FieldMapping, LLMFieldMapping, LLMMappingAnswer
from smart_csv_mapper.schema import FIELDS_BY_NAME, validate_value
from smart_csv_mapper.transforms.catalog import LLM_TRANSFORMS, TransformSpec, apply, check_params
from smart_csv_mapper.transforms.result import Err


def looks_like_full_names(samples: list[str]) -> bool:
    """At least half of the samples have two or more words (or a 'Surname, First' comma)."""
    multi = [s for s in samples if len(s.replace(",", " ").split()) >= 2]
    return len(samples) > 0 and len(multi) * 2 >= len(samples)


def dry_run(item: LLMFieldMapping, spec: TransformSpec, column: ColumnProfile) -> str | None:
    """Try the chosen transform (and the field's validation) on the column's samples.

    Rejects the choice when half or more of the samples fail: e.g. parse_eu_number on
    '1,250.50', or a date format that doesn't match. This checks the model's answer
    against the data, not against its own words.
    """
    if spec.kind == "ai":
        if not looks_like_full_names(column.samples):
            example = column.samples[0]
            return (
                f"column {column.name!r} holds single names (e.g. {example!r}), "
                f"not full names; use trim"
            )
        return None
    failures = []
    for sample in column.samples:
        result = apply(item.transform, sample, item.params)
        if not isinstance(result, Err):
            result = validate_value(item.target, result.value)
        if isinstance(result, Err):
            failures.append(f"{sample!r} ({result.reason})")
    if failures and len(failures) * 2 >= len(column.samples):
        return f"{item.transform} fails on the samples: {'; '.join(failures[:3])}"
    return None


def validate_answer(
    answer: LLMMappingAnswer, columns: list[ColumnProfile]
) -> tuple[dict[str, FieldMapping], list[str]]:
    """Return the usable mappings by target, and the problems to send back to the model."""
    by_lower = {c.name.lower(): c.name for c in columns}
    by_name = {c.name: c for c in columns}
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
        target = FIELDS_BY_NAME[item.target]
        if item.transform not in target.fitting_transforms:
            errors.append(
                f"{item.target}: {item.transform} does not fit a {target.type} field; "
                f"use {' or '.join(target.fitting_transforms)}"
            )
            continue
        problem = check_params(spec, item.params)
        if problem is None:
            problem = dry_run(item, spec, by_name[source])
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
