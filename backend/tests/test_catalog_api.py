from fastapi.testclient import TestClient


def test_schema_endpoint_lists_target_fields(client: TestClient) -> None:
    body = client.get("/schema").json()
    assert body[0] == {
        "name": "external_id",
        "type": "string",
        "required": True,
        "description": "The client's own id for the debtor.",
    }
    assert len(body) == 7


def test_transforms_endpoint_lists_the_closed_catalog(client: TestClient) -> None:
    body = {t["name"]: t for t in client.get("/transforms").json()}
    assert set(body) == {
        "trim",
        "lowercase_trim",
        "parse_eu_number",
        "parse_us_number",
        "parse_date",
        "normalize_phone",
        "constant",
        "map_values",
    }
    assert body["parse_date"]["required_params"] == ["format"]
    assert body["normalize_phone"]["optional_params"] == ["default_country"]
    assert body["map_values"]["free_params"] is True
    assert body["trim"]["llm_allowed"] is True
    assert body["constant"]["llm_allowed"] is False
    assert body["map_values"]["llm_allowed"] is False
