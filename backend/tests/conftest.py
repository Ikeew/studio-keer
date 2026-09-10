import os
from collections.abc import Generator
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from pathlib import Path

# Definido antes de qualquer import da app: Settings é lido no import de
# app.db.session e fica em cache por lru_cache.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://keer:keer@localhost:5432/keer_test")
os.environ.setdefault("SECRET_KEY", "chave-de-teste-com-no-minimo-32-caracteres!")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import sqlalchemy as sa
from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_senha
from app.db.session import get_db
from app.main import app
from app.models.configuracao import Configuracao, HorarioFuncionamento
from app.models.enrollment import Enrollment
from app.models.patient import Patient
from app.models.service import ModeloCobranca, Service
from app.models.session import Session as Sessao
from app.models.user import Papel, User
from app.services.schedule_service import FUSO

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
    """Banco de teste montado pelas MIGRATIONS, não por create_all.

    Duas razões:

    1. `create_all` não roda `CREATE EXTENSION pg_trgm`, nem nada que só
       exista na migration — o índice trigram de pacientes quebraria.
    2. Rodando as migrations, a suíte testa de graça que elas aplicam do zero
       e que o schema resultante é o mesmo que o dos models. Divergência entre
       model e migration vira teste vermelho, não surpresa em produção.
    """
    _criar_banco_de_teste_se_preciso()
    eng = sa.create_engine(str(settings.DATABASE_URL))

    with eng.begin() as conn:
        conn.execute(sa.text("DROP SCHEMA public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))

    config = AlembicConfig(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))
    alembic_upgrade(config, "head")

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


def criar_paciente(db: Session, nome: str = "Paciente Teste") -> Patient:
    paciente = Patient(nome_completo=nome)
    db.add(paciente)
    db.flush()
    return paciente


def criar_configuracao(db: Session) -> None:
    """Grade de funcionamento igual à do seed: seg-sáb 06-21, pausa 12-14."""
    if db.get(Configuracao, 1) is None:
        db.add(Configuracao(id=1))
    for dia in range(7):
        if db.get(HorarioFuncionamento, dia) is not None:
            continue
        db.add(
            HorarioFuncionamento(
                dia_semana=dia,
                aberto=dia != 0,  # domingo fechado
                hora_abertura=dt_time(6, 0),
                hora_fechamento=dt_time(21, 0),
                pausa_inicio=dt_time(12, 0),
                pausa_fim=dt_time(14, 0),
            )
        )
    db.flush()


def proxima_segunda() -> date:
    """Segunda-feira futura, para os testes não esbarrarem no dia de hoje."""
    hoje = date.today()
    return hoje + timedelta(days=(7 - hoje.weekday()) % 7 or 7)


def criar_sessao(
    db: Session,
    instrutor: User,
    *,
    servico: Service | None = None,
    dia: date | None = None,
    hora: int = 8,
    capacidade: int = 4,
) -> Sessao:
    servico = servico or criar_servico(db, nome=f"Servico {hora}-{capacidade}-{dia}")
    quando = datetime.combine(dia or proxima_segunda(), dt_time(hour=hora), tzinfo=FUSO)
    sessao = Sessao(
        service_id=servico.id,
        professional_id=instrutor.id,
        inicia_em=quando,
        termina_em=quando + timedelta(minutes=60),
        capacidade=capacidade,
    )
    db.add(sessao)
    db.flush()
    return sessao


def criar_matricula(
    db: Session,
    paciente: Patient,
    instrutor: User,
    servico: Service,
    *,
    horarios: list[tuple[int, dt_time]] | None = None,
    inicio: date | None = None,
) -> Enrollment:
    from app.services import enrollment_service

    return enrollment_service.criar(
        db,
        patient_id=paciente.id,
        service_id=servico.id,
        professional_id=instrutor.id,
        vigencia_inicio=inicio or date.today(),
        valor_mensal_centavos=20_000,
        horarios=horarios or [(1, dt_time(8, 0))],  # segunda 08:00
    )


def login(client: TestClient, email: str, senha: str = SENHA_PADRAO) -> str:
    """Faz login e devolve o access token."""
    r = client.post("/api/v1/auth/login", data={"username": email, "password": senha})
    assert r.status_code == 200, r.text
    return str(r.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
