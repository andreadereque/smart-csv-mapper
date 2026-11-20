from helpers import SPANISH_COLUMNS, column, good_answer

from smart_csv_mapper.llm.base import LLMError
from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.mapping.models import FieldMapping
from smart_csv_mapper.mapping.suggest import calibrate, suggest_mapping


async def test_valid_first_answer_is_used_as_is() -> None:
    llm = FakeProvider([good_answer()])
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, llm)
    assert proposal.attempts == 1
    assert proposal.warnings == []
    assert [f.origin for f in proposal.fields] == ["llm"] * 7
    assert proposal.model == "fake-model"
    assert proposal.prompt_version == "mapping_v2"
    assert len(llm.prompts) == 1


async def test_invalid_answer_is_retried_with_the_errors_then_accepted() -> None:
    bad = good_answer()
    bad["mappings"][3]["source"] = "Mail"  # type: ignore[index]
    llm = FakeProvider([bad, good_answer()])
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, llm)
    assert proposal.attempts == 2
    assert "column 'Mail' does not exist" in llm.prompts[1]
    assert "previous answer was rejected" not in llm.prompts[0]
    assert proposal.fields[3].source == "Correo"


async def test_schema_mismatch_is_retried_with_a_readable_error() -> None:
    llm = FakeProvider([{"mappings": "nope"}, good_answer()])
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, llm)
    assert proposal.attempts == 2
    assert "answer does not match the schema" in llm.prompts[1]


async def test_two_bad_answers_fall_back_to_heuristics() -> None:
    llm = FakeProvider([{"mappings": "nope"}, {"oops": 1}])
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, llm)
    assert proposal.attempts == 2
    assert proposal.warnings == ["The model's answer was invalid twice; used heuristics."]
    assert {f.origin for f in proposal.fields} == {"heuristic"}
    assert proposal.fields[3].source == "Correo"


async def test_model_down_falls_back_to_heuristics_without_retrying() -> None:
    llm = FakeProvider([LLMError("unavailable", "refused")])
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, llm)
    assert proposal.attempts == 1
    assert proposal.warnings == ["The model is not available (unavailable); used heuristics."]
    assert proposal.fields[0].source == "Referencia"


async def test_fields_the_model_left_empty_are_filled_by_heuristics() -> None:
    answer = good_answer()
    answer["mappings"] = [m for m in answer["mappings"] if m["target"] != "phone"]  # type: ignore[attr-defined]
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, FakeProvider([answer]))
    phone = proposal.fields[4]
    assert (phone.source, phone.origin) == ("Tlf", "heuristic")
    assert proposal.fields[3].origin == "llm"


async def test_required_fields_without_a_column_raise_a_warning() -> None:
    llm = FakeProvider([LLMError("timeout", "slow")])
    proposal = await suggest_mapping("f1", [column("Correo", "a@b.com")], llm)
    assert "Required field 'external_id' has no column yet." in proposal.warnings
    assert "Required field 'amount_due' has no column yet." in proposal.warnings
    assert not any("'email'" in w for w in proposal.warnings)
    assert not any("'phone'" in w for w in proposal.warnings)


def test_confidence_is_kept_when_the_heuristic_agrees() -> None:
    mapping = FieldMapping(target="email", source="Correo", confidence=1.0, origin="llm")
    assert calibrate(mapping, SPANISH_COLUMNS).confidence == 1.0


def test_confidence_is_capped_when_the_heuristic_disagrees_or_has_no_idea() -> None:
    disagrees = FieldMapping(target="email", source="Nombre", confidence=1.0, origin="llm")
    assert calibrate(disagrees, SPANISH_COLUMNS).confidence == 0.6
    unknown = FieldMapping(target="email", source="X", confidence=0.4, origin="llm")
    assert calibrate(unknown, [column("X", "a@b.com")]).confidence == 0.4


async def test_proposal_applies_calibration_to_model_answers() -> None:
    answer = good_answer()
    answer["mappings"][1]["source"] = "Apellidos"  # type: ignore[index]
    proposal = await suggest_mapping("f1", SPANISH_COLUMNS, FakeProvider([answer]))
    assert proposal.fields[1].confidence == 0.6
    assert proposal.fields[2].confidence == 0.95


async def test_heuristic_fill_skips_columns_the_model_already_used() -> None:
    columns = [column("Account", "X1"), column("Amount Due", "100.00", "35.99")]
    answer = {
        "mappings": [
            {
                "target": "external_id",
                "source": "Account",
                "transform": "trim",
                "params": {},
                "confidence": 0.9,
            },
            {
                "target": "amount_due",
                "source": "Amount Due",
                "transform": "parse_us_number",
                "params": {},
                "confidence": 0.9,
            },
        ]
    }
    proposal = await suggest_mapping("f1", columns, FakeProvider([answer]))
    due_date = proposal.fields[6]
    assert (due_date.target, due_date.source) == ("due_date", None)
