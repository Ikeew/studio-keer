from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.package import Package, StatusPacote
from app.models.patient import Patient
from app.models.service import ModeloCobranca, Service
from app.models.user import User
from app.services import package_service
from tests.conftest import criar_servico


def criar_pacote(
    db: Session,
    admin: User,
    *,
    sessoes: int = 10,
    validade: date | None = None,
    status: StatusPacote = StatusPacote.ATIVO,
) -> Package:
    paciente = Patient(nome_completo="Paciente Teste")
    db.add(paciente)
    servico = criar_servico(db, nome=f"Fisio {sessoes}-{validade}-{status}")
    db.flush()

    pacote = Package(
        patient_id=paciente.id,
        service_id=servico.id,
        sessoes_contratadas=sessoes,
        valor_centavos=100_000,
        validade_ate=validade,
        comprado_em=date.today(),
        registrado_por_id=admin.id,
        status=status,
    )
    db.add(pacote)
    db.flush()
    return pacote


class TestSaldo:
    def test_pacote_novo_tem_saldo_cheio(self, db: Session, admin: User) -> None:
        pacote = criar_pacote(db, admin, sessoes=10)

        assert package_service.saldo(db, pacote) == 10

    def test_saldo_nao_e_coluna(self, db: Session, admin: User) -> None:
        """Saldo é contagem em query — coluna sairia de sincronia."""
        pacote = criar_pacote(db, admin)

        assert not hasattr(pacote, "saldo")


class TestValidade:
    def test_validade_nula_significa_vale_ate_acabar(self, db: Session, admin: User) -> None:
        """Nulo é caso normal, não dado faltando."""
        pacote = criar_pacote(db, admin, validade=None)

        assert package_service.dentro_da_validade(pacote)
        assert package_service.utilizavel(db, pacote)

    def test_validade_futura_e_valida(self, db: Session, admin: User) -> None:
        pacote = criar_pacote(db, admin, validade=date.today() + timedelta(days=30))

        assert package_service.utilizavel(db, pacote)

    def test_validade_hoje_ainda_vale(self, db: Session, admin: User) -> None:
        pacote = criar_pacote(db, admin, validade=date.today())

        assert package_service.dentro_da_validade(pacote)

    def test_validade_vencida_bloqueia_mesmo_com_saldo(self, db: Session, admin: User) -> None:
        """A trava central do pacote.

        Como falta NÃO consome sessão (decisão da cliente), quem falta muito
        mantém o saldo intacto para sempre. A validade é a única trava — por
        isso `utilizavel` nunca olha só o saldo.
        """
        pacote = criar_pacote(db, admin, sessoes=10, validade=date.today() - timedelta(days=1))

        assert package_service.saldo(db, pacote) == 10, "saldo continua cheio"
        assert not package_service.utilizavel(db, pacote), "mas o pacote não serve mais"

    def test_pacote_cancelado_nao_e_utilizavel(self, db: Session, admin: User) -> None:
        pacote = criar_pacote(db, admin, status=StatusPacote.CANCELADO)

        assert not package_service.utilizavel(db, pacote)


class TestSnapshot:
    def test_valores_nao_vem_do_servico(self, db: Session, admin: User) -> None:
        """O pacote captura os valores no ato da venda e nunca os relê.

        Reajustar a sugestão do serviço não pode alterar o que já foi
        combinado com o paciente.
        """
        pacote = criar_pacote(db, admin, sessoes=7)

        servico = db.get(Service, pacote.service_id)
        assert servico is not None
        servico.modelo_cobranca = ModeloCobranca.PACOTE
        servico.sugestao_pacote_sessoes = 99
        servico.preco_centavos = 999_999
        db.flush()

        assert pacote.sessoes_contratadas == 7
        assert pacote.valor_centavos == 100_000
