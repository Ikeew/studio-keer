import os
from collections.abc import Generator

# Definido antes de qualquer import da app: Settings é lido no import de
# app.db.session e fica em cache por lru_cache.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://keer:keer@localhost:5432/keer_test")
os.environ.setdefault("SECRET_KEY", "chave-de-teste-com-no-minimo-32-caracteres!")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_senha
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.service import ModeloCobranca, Service
from app.models.user import Papel, User

settings = get_settings()

SENHA_PADRAO = "senha-de-teste-123"


def _criar_banco_de_teste_se_preciso() -> None:
    """Cria o database de teste, conectando ao `postgres` de manutenção.

    Deixa a suíte rodar com um `docker compose up db` limpo, sem passo manual
    de preparação que alguém da equipe vá esquecer.
    """
    url = sa.engine.make_url(str(settings.DATABASE_URL))
    nome = url.database
    admin = sa.create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        existe = conn.execute(
            sa.text("select 1 from pg_database where datname = :n"), {"n": nome}
        ).scalar()
        if not existe:
            conn.execute(sa.text(f'create database "{nome}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine() -> Generator[sa.Engine, None, None]:
    _criar_banco_de_teste_se_preciso()
    eng = sa.create_engine(str(settings.DATABASE_URL))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: sa.Engine) -> Generator[Session, None, None]:
    """Sessão isolada por teste.

    Cada teste roda dentro de uma transação revertida no fim, então um teste
    nunca enxerga dado criado por outro e a ordem de execução não importa.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = sessionmaker(bind=conn, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP que compartilha a transação do teste."""

    def _get_db_override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def criar_usuario(
    db: Session,
    papel: Papel,
    *,
    email: str | None = None,
    senha: str = SENHA_PADRAO,
    ativo: bool = True,
) -> User:
    user = User(
        nome=f"Teste {papel.value}",
        email=email or f"{papel.value}@example.com",
        senha_hash=hash_senha(senha),
        papel=papel,
        ativo=ativo,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def admin(db: Session) -> User:
    return criar_usuario(db, Papel.ADMIN)


@pytest.fixture
def recepcao(db: Session) -> User:
    return criar_usuario(db, Papel.RECEPCAO)


@pytest.fixture
def instrutor(db: Session) -> User:
    return criar_usuario(db, Papel.INSTRUTOR)


def criar_servico(
    db: Session,
    *,
    nome: str = "Pilates",
    modelo: ModeloCobranca = ModeloCobranca.MENSALIDADE,
    capacidade: int = 4,
) -> Service:
    servico = Service(
        nome=nome,
        duracao_min=60,
        preco_centavos=10_000,
        capacidade_padrao=capacidade,
        cor="#06B6D4",
        modelo_cobranca=modelo,
    )
    db.add(servico)
    db.flush()
    return servico


def login(client: TestClient, email: str, senha: str = SENHA_PADRAO) -> str:
    """Faz login e devolve o access token."""
    r = client.post("/api/v1/auth/login", data={"username": email, "password": senha})
    assert r.status_code == 200, r.text
    return str(r.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
