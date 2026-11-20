"""Ask the model for a mapping; validate it; retry once with the errors; fall back to heuristics."""

import logging

from pydantic import ValidationError

from smart_csv_mapper.ingest.profile import ColumnProfile
from smart_csv_mapper.llm.base import LLMError, LLMProvider
from smart_csv_mapper.mapping.heuristic import heuristic_field
from smart_csv_mapper.mapping.models import FieldMapping, LLMMappingAnswer, MappingProposal
from smart_csv_mapper.mapping.prompt import PROMPT_VERSION, answer_schema, build_prompt
from smart_csv_mapper.mapping.validate import validate_answer
from smart_csv_mapper.schema import TARGET_SCHEMA

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 2
UNCONFIRMED_CONFIDENCE_CAP = 0.6


def calibrate(mapping: FieldMapping, columns: list[ColumnProfile]) -> FieldMapping:
    """Small models report ~1.0 for everything. Only keep a high score when the header
    heuristic points to the same column; otherwise cap it so the UI asks for a review."""
    second_opinion = heuristic_field(mapping.target, columns)
    if second_opinion.source == mapping.source:
        return mapping
    capped = min(mapping.confidence, UNCONFIRMED_CONFIDENCE_CAP)
    return mapping.model_copy(update={"confidence": capped})


async def _ask_model(
    llm: LLMProvider, columns: list[ColumnProfile]
) -> tuple[dict[str, FieldMapping], int, list[str]]:
    """Return accepted mappings, attempts used, and warnings. Empty mappings = model failed."""
    errors: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await llm.complete_json(build_prompt(columns, errors), answer_schema())
            answer = LLMMappingAnswer.model_validate(response.data)
        except LLMError as error:
            return {}, attempt, [f"The model is not available ({error.kind}); used heuristics."]
        except ValidationError as error:
            errors = [
                f"answer does not match the schema: {e['msg']} at {e['loc']}"
                for e in error.errors()[:5]
            ]
            continue
        accepted, errors = validate_answer(answer, columns)
        if not errors:
            return accepted, attempt, []
    logger.info("mapping_rejected", extra={"extra_fields": {"errors": errors}})
    return {}, MAX_ATTEMPTS, ["The model's answer was invalid twice; used heuristics."]


async def suggest_mapping(
    file_id: str, columns: list[ColumnProfile], llm: LLMProvider
) -> MappingProposal:
    from_model, attempts, warnings = await _ask_model(llm, columns)
    taken = frozenset(m.source for m in from_model.values() if m.source is not None)
    fields = []
    for target in TARGET_SCHEMA:
        mapping = from_model.get(target.name)
        if mapping is None:
            mapping = heuristic_field(target.name, columns, taken)
        else:
            mapping = calibrate(mapping, columns)
        if mapping.source is None and target.required:
            warnings.append(f"Required field {target.name!r} has no column yet.")
        fields.append(mapping)
    return MappingProposal(
        file_id=file_id,
        fields=fields,
        warnings=warnings,
        prompt_version=PROMPT_VERSION,
        model=llm.model,
        attempts=attempts,
    )
