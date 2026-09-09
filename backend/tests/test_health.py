from fastapi.testclient import TestClient


def test_health_responde_200(client: TestClient) -> None:
    r = client.get("/api/v1/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_reporta_estado_do_banco(client: TestClient) -> None:
    """O endpoint sobe mesmo sem Postgres; o campo `database` denuncia."""
    r = client.get("/api/v1/health")

    assert r.json()["database"] in {"ok", "unreachable"}
