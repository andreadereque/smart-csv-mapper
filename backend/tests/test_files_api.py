from conftest import fixture_bytes
from fastapi.testclient import TestClient


def _upload(client: TestClient, name: str, content: bytes):  # type: ignore[no-untyped-def]
    return client.post("/files", files={"file": (name, content, "text/csv")})


def test_upload_returns_the_column_profile(client: TestClient) -> None:
    response = _upload(client, "clientes_es.csv", fixture_bytes("clientes_es.csv"))
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "clientes_es.csv"
    assert body["row_count"] == 2
    assert [c["name"] for c in body["columns"]] == [
        "Nombre completo",
        "Correo",
        "Tlf",
        "Importe (€)",
    ]
    assert body["columns"][0]["samples"] == ["María López García", "José de la Fuente"]


def test_uploaded_file_can_be_read_back(client: TestClient) -> None:
    file_id = _upload(client, "a.csv", b"a,b\n1,2\n").json()["file_id"]
    response = client.get(f"/files/{file_id}")
    assert response.status_code == 200
    assert response.json()["file_id"] == file_id


def test_unknown_file_is_404(client: TestClient) -> None:
    assert client.get("/files/does-not-exist").status_code == 404


def test_rejects_unsupported_extension(client: TestClient) -> None:
    response = _upload(client, "data.xlsx", b"a,b\n1,2\n")
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_file_type"


def test_rejects_files_over_the_size_limit(client: TestClient) -> None:
    big = b"a\n" + b"x" * (1024 * 1024)
    response = _upload(client, "big.csv", big)
    assert response.status_code == 413


def test_accepts_a_file_exactly_at_the_size_limit(client: TestClient) -> None:
    rows = [b"x" * 10_000 + b"\n"] * 99
    rest = 1024 * 1024 - 2 - len(b"".join(rows))
    body = b"a\n" + b"".join(rows) + b"x" * (rest - 1) + b"\n"
    assert len(body) == 1024 * 1024
    assert _upload(client, "edge.csv", body).status_code == 201


def test_parse_errors_are_422_with_a_code(client: TestClient) -> None:
    response = _upload(client, "dup.csv", b"Email,email\n1,2\n")
    assert response.status_code == 422
    assert response.json() == {
        "code": "duplicate_header",
        "detail": "Duplicate column header: 'email'.",
    }


def test_upload_without_a_filename_is_rejected(client: TestClient) -> None:
    response = client.post("/files", files={"file": ("", b"a\n1\n", "text/csv")})
    assert response.status_code == 422


def test_a_huge_single_field_is_422_not_500(client: TestClient) -> None:
    response = _upload(client, "huge.csv", b"a\n" + b"x" * 200_000 + b"\n")
    assert response.status_code == 422
    assert response.json()["code"] == "malformed_csv"


def test_extension_check_ignores_case(client: TestClient) -> None:
    assert _upload(client, "DATA.CSV", b"a,b\n1,2\n").status_code == 201
