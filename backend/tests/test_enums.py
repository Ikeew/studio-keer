"""Enum lido do banco tem de voltar como Enum, não como str.

Regressão real: as colunas de enum eram `String(16)` com anotação
`Mapped[MeuEnum]`. O valor era gravado certo, mas voltava como `str`, e toda
comparação `x.status is MeuEnum.ALGO` virava False em silêncio.

Não aparecia nos testes porque objeto criado e lido na mesma sessão continua
sendo o mesmo objeto Python. Só um reload de verdade expõe o problema — por
isso `db.expunge` e `db.get` abaixo.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.package import Package, StatusPacote
from app.models.patient import EstadoCivil, Patient, Sexo
from app.models.service import ModeloCobranca, Service
from app.models.session import Session as Sessao
from app.models.session import StatusSessao
from app.models.user import Papel, User
from app.services import package_service
from tests.conftest import criar_paciente, criar_servico, criar_sessao


def _recarregar[T](db: Session, modelo: type[T], obj_ou_pk: object) -> T:
    """Força ida ao banco, em vez de devolver o objeto do identity map."""
    db.flush()  # antes de ler o id: sem isso a PK ainda é None
    pk = getattr(obj_ou_pk, "id", obj_ou_pk)
    db.expire_all()
    obj = db.get(modelo, pk)
    assert obj is not None
    return obj


def test_papel_do_usuario(db: Session, recepcao: User) -> None:
    recarregado = _recarregar(db, User, recepcao.id)

    assert recarregado.papel is Papel.RECEPCAO


def test_sexo_e_estado_civil_do_paciente(db: Session) -> None:
    paciente = Patient(
        nome_completo="Enum Teste", sexo=Sexo.FEMININO, estado_civil=EstadoCivil.CASADO
    )
    db.add(paciente)

    recarregado = _recarregar(db, Patient, paciente)

    assert recarregado.sexo is Sexo.FEMININO
    assert recarregado.estado_civil is EstadoCivil.CASADO


def test_modelo_de_cobranca_do_servico(db: Session) -> None:
    servico = criar_servico(db, nome="Enum Servico", modelo=ModeloCobranca.PACOTE)

    recarregado = _recarregar(db, Service, servico.id)

    assert recarregado.modelo_cobranca is ModeloCobranca.PACOTE


def test_status_da_sessao_e_da_reserva(db: Session, instrutor: User, recepcao: User) -> None:
    sessao = criar_sessao(db, instrutor)
    reserva = Booking(
        session_id=sessao.id,
        patient_id=criar_paciente(db, "Enum Reserva").id,
        posicao=1,
        capacidade_sessao=4,
        origem=OrigemReserva.REPOSICAO,
        status=StatusReserva.CONFIRMADA,
        criado_por_id=recepcao.id,
    )
    db.add(reserva)

    s = _recarregar(db, Sessao, sessao.id)
    b = _recarregar(db, Booking, reserva)

    assert s.status is StatusSessao.AGENDADA
    assert b.status is StatusReserva.CONFIRMADA
    assert b.origem is OrigemReserva.REPOSICAO


def test_pacote_recarregado_continua_utilizavel(db: Session, admin: User) -> None:
    """O caso que o bug quebrava de verdade.

    `package_service.utilizavel` compara `status is StatusPacote.ATIVO`. Com o
    status voltando como str, um pacote válido recarregado do banco era
    considerado inutilizável — e a recepção não conseguiria agendar.
    """
    servico = criar_servico(db, nome="Enum Pacote", modelo=ModeloCobranca.PACOTE)
    pacote = Package(
        patient_id=criar_paciente(db, "Dono do Pacote").id,
        service_id=servico.id,
        sessoes_contratadas=10,
        valor_centavos=100_000,
        validade_ate=date.today() + timedelta(days=30),
        comprado_em=date.today(),
        registrado_por_id=admin.id,
        status=StatusPacote.ATIVO,
    )
    db.add(pacote)

    recarregado = _recarregar(db, Package, pacote)

    assert recarregado.status is StatusPacote.ATIVO
    assert package_service.utilizavel(db, recarregado) is True


def test_datas_voltam_com_fuso(db: Session, instrutor: User) -> None:
    """TIMESTAMPTZ nunca pode voltar ingênuo — senão a agenda desanda."""
    sessao = criar_sessao(db, instrutor)

    recarregada = _recarregar(db, Sessao, sessao.id)

    assert recarregada.inicia_em.tzinfo is not None
    assert isinstance(recarregada.inicia_em, datetime)
    assert isinstance(time(8, 0), time)


class TestTodosOsModelsDeclaramEnumCorretamente:
    """Rede permanente contra o bug do enum.

    A varredura por grep encontra o que existe hoje; este teste pega o model
    que alguém escrever amanhã. Percorre TODOS os models mapeados e exige que
    toda coluna cujo tipo Python é um StrEnum use `sa.Enum` — nunca `String`.
    """

    def test_nenhuma_coluna_de_enum_usa_string(self) -> None:
        import sqlalchemy as sa

        from app.db.base import Base

        problemas: list[str] = []

        for mapper in Base.registry.mappers:
            for prop in mapper.column_attrs:
                anotacao = mapper.class_.__annotations__.get(prop.key, "")
                texto = str(anotacao)
                # Colunas anotadas com um enum do domínio.
                if not any(
                    nome in texto
                    for nome in (
                        "Papel",
                        "Sexo",
                        "EstadoCivil",
                        "ModeloCobranca",
                        "StatusPacote",
                        "StatusSessao",
                        "StatusReserva",
                        "OrigemReserva",
                    )
                ):
                    continue
                coluna = prop.columns[0]
                if not isinstance(coluna.type, sa.Enum):
                    problemas.append(
                        f"{mapper.class_.__name__}.{prop.key} usa "
                        f"{type(coluna.type).__name__} — use coluna_enum(...)"
                    )

        assert not problemas, "\n".join(problemas)

    def test_todo_enum_do_dominio_tem_teste_de_reload(self) -> None:
        """Lembrete: enum novo precisa entrar nos testes de reload acima."""
        from app.models.booking import OrigemReserva, StatusReserva
        from app.models.package import StatusPacote
        from app.models.patient import EstadoCivil, Sexo
        from app.models.service import ModeloCobranca
        from app.models.session import StatusSessao
        from app.models.user import Papel

        cobertos = {
            Papel,
            Sexo,
            EstadoCivil,
            ModeloCobranca,
            StatusPacote,
            StatusSessao,
            StatusReserva,
            OrigemReserva,
        }

        assert len(cobertos) == 8, (
            "Enum novo no domínio? Some ao conjunto e escreva o teste de reload."
        )
