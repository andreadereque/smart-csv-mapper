"""Build the mapping prompt from the schema, the transform catalog and the column profiles."""

import json
from importlib import resources

from smart_csv_mapper.ingest.profile import ColumnProfile
from smart_csv_mapper.schema import TARGET_SCHEMA
from smart_csv_mapper.transforms.catalog import LLM_TRANSFORMS

PROMPT_VERSION = "mapping_v2"
TEMPLATE = resources.files("smart_csv_mapper.mapping.prompts").joinpath(f"{PROMPT_VERSION}.md")


def _schema_lines() -> str:
    lines = []
    for field in TARGET_SCHEMA:
        required = "optional"
        if field.required:
            required = "required"
        allowed = " or ".join(field.fitting_transforms)
        lines.append(
            f"- {field.name} ({field.type}, {required}): {field.description} Transform: {allowed}."
        )
    return "\n".join(lines)


def _transform_lines() -> str:
    lines = []
    for spec in LLM_TRANSFORMS.values():
        params = list(spec.required_params) + [f"{p}?" for p in spec.optional_params]
        suffix = ""
        if params:
            suffix = f" Params: {', '.join(params)}."
        lines.append(f"- {spec.name}: {spec.description}{suffix}")
    return "\n".join(lines)


def build_prompt(columns: list[ColumnProfile], previous_errors: list[str] | None = None) -> str:
    errors_section = ""
    if previous_errors:
        listed = "\n".join(f"- {e}" for e in previous_errors)
        errors_section = (
            "\n## Your previous answer was rejected\nFix these problems and answer again:\n"
            f"{listed}\n"
        )
    columns_json = json.dumps([c.model_dump() for c in columns], ensure_ascii=False, indent=1)
    return TEMPLATE.read_text(encoding="utf-8").format(
        schema=_schema_lines(),
        transforms=_transform_lines(),
        columns=columns_json,
        targets=", ".join(f.name for f in TARGET_SCHEMA),
        previous_errors=errors_section,
    )


def answer_schema() -> dict[str, object]:
    """JSON Schema for the model's answer, with enums so a small model can't drift."""
    item = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": [f.name for f in TARGET_SCHEMA]},
            "source": {"type": ["string", "null"]},
            "transform": {"type": "string", "enum": list(LLM_TRANSFORMS)},
            "params": {"type": "object", "additionalProperties": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["target", "source", "transform", "params", "confidence"],
    }
    return {
        "type": "object",
        "properties": {"mappings": {"type": "array", "items": item}},
        "required": ["mappings"],
    }
