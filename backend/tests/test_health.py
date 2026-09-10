from fastapi.testclient import TestClient


def test_health_responde_200(client: TestClient) -> None:
    r = client.get("/api/v1/health")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_reporta_estado_do_banco(client: TestClient) -> None:
    """O endpoint sobe mesmo sem Postgres; o campo `database` denuncia."""
    r = client.get("/api/v1/health")

    assert r.json()["database"] in {"ok", "unreachable"}


class TestUrlDoBanco:
    """Render e Railway entregam `postgres://`, que o SQLAlchemy 2.0 recusa.

    Sem normalização a app subiria e morreria na primeira query, já em
    produção — o tipo de erro que só aparece depois do deploy.
    """

    def test_normaliza_o_esquema_dos_provedores(self) -> None:
        from app.core.config import Settings

        for url in (
            "postgres://u:p@host:5432/base",
            "postgresql://u:p@host:5432/base",
            "postgresql+psycopg://u:p@host:5432/base",
        ):
            s = Settings(DATABASE_URL=url, SECRET_KEY="x" * 40)  # type: ignore[arg-type]
            assert str(s.DATABASE_URL).startswith("postgresql+psycopg://"), url
