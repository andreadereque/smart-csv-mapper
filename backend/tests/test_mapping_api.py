from conftest import fixture_bytes
from fastapi.testclient import TestClient
from helpers import good_answer

from smart_csv_mapper.llm.fake import FakeProvider


def test_suggest_returns_a_proposal_for_an_uploaded_file(client: TestClient) -> None:
    upload = client.post(
        "/files", files={"file": ("c.csv", fixture_bytes("clientes_es.csv"), "text/csv")}
    )
    file_id = upload.json()["file_id"]
    llm: FakeProvider = client.app.state.llm  # type: ignore[attr-defined]
    answer = good_answer()
    answer["mappings"] = [  # only columns that exist in clientes_es.csv
        {
            "target": "email",
            "source": "Correo",
            "transform": "lowercase_trim",
            "params": {},
            "confidence": 0.9,
        }
    ]
    llm.answers.append(answer)
    response = client.post(f"/files/{file_id}/suggest")
    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == file_id
    by_target = {f["target"]: f for f in body["fields"]}
    assert by_target["email"]["origin"] == "llm"
    assert by_target["phone"]["source"] == "Tlf"
    assert by_target["phone"]["origin"] == "heuristic"
    assert '"name": "Nombre completo"' in llm.prompts[0]


def test_suggest_for_an_unknown_file_is_404(client: TestClient) -> None:
    assert client.post("/files/nope/suggest").status_code == 404
