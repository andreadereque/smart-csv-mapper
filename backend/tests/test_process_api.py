from fastapi.testclient import TestClient
from test_pipeline import mapping, splitter_answer

from smart_csv_mapper.llm.fake import FakeProvider
from smart_csv_mapper.mapping.models import FieldMapping

CSV = (
    b"Ref,Nombre completo,Correo,Tlf,Importe,Vence\n"
    b'C-1,Ana Ruiz,ANA@EXAMPLE.COM,612 345 678,"1.250,50",20/11/2026\n'
    b'C-2,Luis Gil,not-an-email,,"80,00",\n'
    b'=cmd,Ana Ruiz,,,"5,00",\n'
)


def upload(client: TestClient) -> str:
    response = client.post("/files", files={"file": ("clients.csv", CSV, "text/csv")})
    return str(response.json()["file_id"])


def script(client: TestClient, *answers: dict[str, object]) -> FakeProvider:
    llm: FakeProvider = client.app.state.llm  # type: ignore[attr-defined]
    llm.answers.extend(answers)
    return llm


def body(**extra: object) -> dict[str, object]:
    return {"fields": [f.model_dump() for f in mapping()], **extra}


def test_preview_returns_the_first_rows_errors_counts_and_ai_stats(client: TestClient) -> None:
    file_id = upload(client)
    script(client, splitter_answer())
    response = client.post(f"/files/{file_id}/preview", json=body(rows=2))
    assert response.status_code == 200
    data = response.json()
    assert data["rows_checked"] == 2
    assert data["rows"][0]["amount_due"] == "1250.50"
    assert data["error_count_by_field"] == {"email": 1}
    assert data["errors"][0]["row"] == 2
    assert data["ai_stats"][0]["llm_calls"] == 1


def test_preview_rejects_an_invalid_mapping(client: TestClient) -> None:
    file_id = upload(client)
    fields = [f.model_dump() for f in mapping(email=FieldMapping(target="email", source="X"))]
    response = client.post(f"/files/{file_id}/preview", json={"fields": fields})
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_mapping",
        "problems": ["email: column 'X' does not exist"],
    }


def test_preview_row_limit_is_validated(client: TestClient) -> None:
    assert client.post(f"/files/{upload(client)}/preview", json=body(rows=0)).status_code == 422


def test_export_with_errors_is_refused_and_explains_them(client: TestClient) -> None:
    file_id = upload(client)
    script(client, splitter_answer())
    response = client.post(f"/files/{file_id}/export", json=body())
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_rows"
    assert detail["invalid_row_count"] == 1
    assert detail["errors"][0]["field"] == "email"
    assert client.get("/audit").json() == []


def test_export_skipping_invalid_rows_returns_safe_csv_and_writes_the_audit_log(
    client: TestClient,
) -> None:
    file_id = upload(client)
    script(client, splitter_answer())
    response = client.post(f"/files/{file_id}/export", json=body(skip_invalid=True))
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="clients_clean.csv"'
    assert response.headers["x-rows-exported"] == "2"
    assert response.headers["x-rows-skipped"] == "1"
    lines = response.text.splitlines()
    assert lines[0] == "external_id,first_name,last_name,email,phone,amount_due,due_date"
    assert lines[1] == "C-1,Ana,Ruiz,ana@example.com,+34612345678,1250.50,2026-11-20"
    assert lines[2] == "'=cmd,Ana,Ruiz,,,5.00,"
    [entry] = client.get("/audit").json()
    assert entry["filename"] == "clients.csv"
    assert len(entry["file_sha256"]) == 64
    assert (entry["rows_total"], entry["rows_exported"], entry["rows_skipped"]) == (3, 2, 1)
    assert entry["model"] == "fake-model"
    assert entry["ai_stats"][0]["distinct"] == 2
    assert entry["mapping"][0]["target"] == "external_id"


def test_export_of_a_clean_file_needs_no_skipping(client: TestClient) -> None:
    file_id = upload(client)
    script(client, splitter_answer())
    fields = mapping(email=FieldMapping(target="email"))
    response = client.post(
        f"/files/{file_id}/export", json={"fields": [f.model_dump() for f in fields]}
    )
    assert response.status_code == 200
    assert response.headers["x-rows-skipped"] == "0"


def test_unknown_file_is_404_everywhere(client: TestClient) -> None:
    assert client.post("/files/nope/preview", json=body()).status_code == 404
    assert client.post("/files/nope/export", json=body()).status_code == 404
