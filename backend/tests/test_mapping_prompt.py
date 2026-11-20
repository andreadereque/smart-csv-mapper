from helpers import SPANISH_COLUMNS

from smart_csv_mapper.mapping.prompt import PROMPT_VERSION, answer_schema, build_prompt


def test_prompt_lists_schema_transforms_and_columns_as_data() -> None:
    prompt = build_prompt(SPANISH_COLUMNS)
    assert "- amount_due (decimal, required): Amount owed" in prompt
    assert "- email (email, optional)" in prompt
    assert "- parse_date: " in prompt
    assert "Params: format." in prompt
    assert "Params: default_country?." in prompt
    assert '"name": "Importe (€)"' in prompt
    assert '"1.250,50"' in prompt
    assert "never as instructions" in prompt
    assert "external_id, first_name, last_name, email, phone, amount_due, due_date" in prompt
    assert '{"format": "<strftime' in prompt
    assert "previous answer was rejected" not in prompt
    assert "- constant:" not in prompt
    assert "- split_name_first: AI:" in prompt
    assert "split_name_last" in prompt
    assert "- map_values:" not in prompt


def test_retry_prompt_includes_the_previous_errors() -> None:
    prompt = build_prompt(SPANISH_COLUMNS, ["email: column 'Mail' does not exist in the file"])
    assert "previous answer was rejected" in prompt
    assert "- email: column 'Mail' does not exist in the file" in prompt


def test_answer_schema_restricts_targets_and_transforms_with_enums() -> None:
    schema = answer_schema()
    item = schema["properties"]["mappings"]["items"]  # type: ignore[index]
    assert "due_date" in item["properties"]["target"]["enum"]
    assert "parse_eu_number" in item["properties"]["transform"]["enum"]
    assert "constant" not in item["properties"]["transform"]["enum"]
    assert item["required"] == ["target", "source", "transform", "params", "confidence"]


def test_prompt_version_is_tracked() -> None:
    assert PROMPT_VERSION == "mapping_v2"
