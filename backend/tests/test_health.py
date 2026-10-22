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

    def test_migrations_usam_a_conexao_direta_do_neon(self) -> None:
        """App no PgBouncer (`-pooler`), Alembic na conexão direta."""
        from app.core.config import Settings

        query = "?sslmode=require&channel_binding=require"
        s = Settings(
            DATABASE_URL="postgresql://u:p@ep-x-pooler.neon.tech/neondb" + query,  # type: ignore[arg-type]
            DATABASE_URL_UNPOOLED="postgresql://u:p@ep-x.neon.tech/neondb" + query,  # type: ignore[arg-type]
            SECRET_KEY="x" * 40,
            _env_file=None,
        )

        assert s.url_migrations == "postgresql+psycopg://u:p@ep-x.neon.tech/neondb" + query
        assert "-pooler" in str(s.DATABASE_URL)

    def test_sem_conexao_direta_as_migrations_usam_a_principal(self) -> None:
        from app.core.config import Settings

        s = Settings(
            DATABASE_URL="postgresql://u:p@db:5432/keer",  # type: ignore[arg-type]
            DATABASE_URL_UNPOOLED=None,
            SECRET_KEY="x" * 40,
            _env_file=None,
        )

        assert s.url_migrations == "postgresql+psycopg://u:p@db:5432/keer"
