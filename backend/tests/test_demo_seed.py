"""O seed de demonstração precisa contar a história toda.

Se algum destes testes quebrar, a apresentação perde uma cena.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.charge import Charge, StatusCobranca
from app.models.enrollment import Enrollment, EnrollmentHorario
from app.models.package import Package
from app.models.patient import Patient
from app.models.user import User
from app.services import demo_service, package_service, reposicao_service
from tests.conftest import criar_configuracao, criar_servico


def _preparar(db: Session, admin: User, recepcao: User, instrutor: User) -> None:
    """O seed exige serviços e usuários já criados."""
    criar_configuracao(db)
    criar_servico(db, nome="Pilates", capacidade=4)
    criar_servico(db, nome="Fisioterapia", capacidade=4)
    db.flush()


class TestHistoriaCompleta:
    def test_cria_pacientes_ativos_e_inativos(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        ativos = db.execute(
            select(func.count()).select_from(Patient).where(Patient.ativo.is_(True))
        ).scalar_one()
        inativos = db.execute(
            select(func.count()).select_from(Patient).where(Patient.ativo.is_(False))
        ).scalar_one()

        assert ativos >= 15, "poucos pacientes: a grade não parece um studio real"
        assert inativos >= 1, "sem inativo, a busca com 'incluir inativos' não mostra nada"

    def test_tem_uma_turma_completa(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """A cena mais forte da apresentação: a quinta matrícula recusada."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        por_slot = db.execute(
            select(
                EnrollmentHorario.dia_semana,
                EnrollmentHorario.hora_inicio,
                func.count(),
            )
            .join(Enrollment, Enrollment.id == EnrollmentHorario.enrollment_id)
            .group_by(EnrollmentHorario.dia_semana, EnrollmentHorario.hora_inicio)
        ).all()

        cheias = [(d, h) for d, h, n in por_slot if n >= 4]
        assert cheias, "nenhuma turma completa: a demonstração da recusa não funciona"

    def test_a_grade_tem_textura(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Horários cheios E vazios. Grade uniforme não demonstra nada."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        ocupacoes = [
            n
            for _, _, n in db.execute(
                select(
                    EnrollmentHorario.dia_semana,
                    EnrollmentHorario.hora_inicio,
                    func.count(),
                )
                .join(Enrollment, Enrollment.id == EnrollmentHorario.enrollment_id)
                .group_by(EnrollmentHorario.dia_semana, EnrollmentHorario.hora_inicio)
            ).all()
        ]

        assert max(ocupacoes) >= 4
        assert min(ocupacoes) <= 2, "todos os horários igualmente cheios: sem textura"

    def test_tem_reposicoes_pendentes(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Sem isto, o painel mais importante aparece vazio na demonstração."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        pendentes = reposicao_service.listar_pendentes(db)

        assert len(pendentes) >= 2

    def test_tem_faltas_dos_dois_tipos(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        justificadas = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(Booking.status == StatusReserva.FALTA, Booking.justificada.is_(True))
        ).scalar_one()
        nao = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(Booking.status == StatusReserva.FALTA, Booking.justificada.is_(False))
        ).scalar_one()

        assert justificadas >= 3
        assert nao >= 1, "sem falta não justificada não há contraste no painel"

    def test_tem_uma_reposicao_ja_feita(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Mostra o vínculo `substitui_booking_id` funcionando."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        feitas = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.origem == OrigemReserva.REPOSICAO,
                Booking.substitui_booking_id.is_not(None),
            )
        ).scalar_one()

        assert feitas >= 1

    def test_tem_cancelamentos_com_motivo(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        com_motivo = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.status == StatusReserva.CANCELADA,
                Booking.motivo_cancelamento.is_not(None),
            )
        ).scalar_one()

        assert com_motivo >= 3


class TestFinanceiroDaDemo:
    def test_cobrancas_nos_tres_estados(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Paga, pendente E vencida — os três cards do topo com número."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)
        hoje = date.today()

        cobrancas = list(db.execute(select(Charge)).scalars())
        pagas = [c for c in cobrancas if c.status is StatusCobranca.PAGO]
        vencidas = [
            c for c in cobrancas if c.status is StatusCobranca.PENDENTE and c.vencimento < hoje
        ]
        pendentes = [
            c for c in cobrancas if c.status is StatusCobranca.PENDENTE and c.vencimento >= hoje
        ]

        assert pagas, "sem cobrança paga o card 'Total Recebido' fica zerado"
        assert vencidas, "sem vencida o card 'Total Vencido' fica zerado"
        assert pendentes, "sem pendente futura, toda pendente estaria vencida"

    def test_vencimentos_em_dias_diferentes_incluindo_31(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Dia 31 é o caso que quebra em meses de 30 dias e em fevereiro."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        dias = {m.dia_vencimento for m in db.execute(select(Enrollment)).scalars()}

        assert len(dias) >= 5, "vencimentos concentrados num dia só"
        assert 31 in dias, "sem paciente do dia 31 o caso difícil não é demonstrado"

    def test_pacotes_com_saldos_diferentes(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        pacotes = list(db.execute(select(Package)).scalars())
        saldos = {package_service.saldo(db, p) for p in pacotes}

        assert len(pacotes) >= 3
        assert len(saldos) >= 2, "todos os pacotes com o mesmo saldo"
        assert any(p.validade_ate is None for p in pacotes), "nenhum sem validade"
        assert any(p.validade_ate is not None for p in pacotes), "nenhum com validade"


class TestDadosFicticios:
    def test_nenhum_cpf_e_valido(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Nenhum CPF pode pertencer a uma pessoa real."""
        from app.core.cpf import cpf_valido

        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        for paciente in db.execute(select(Patient)).scalars():
            if paciente.cpf:
                assert not cpf_valido(paciente.cpf), (
                    f"{paciente.nome_completo} tem CPF VÁLIDO — pode ser de alguém real"
                )

    def test_telefones_usam_prefixo_reservado(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        for paciente in db.execute(select(Patient)).scalars():
            if paciente.telefone:
                assert "5550" in paciente.telefone, (
                    f"{paciente.nome_completo}: telefone pode existir de verdade"
                )

    def test_pacientes_marcados_como_demo(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """A marca é o que permite limpar sem tocar em dado digitado à mão."""
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        for paciente in db.execute(select(Patient)).scalars():
            assert paciente.observacoes is not None
            assert paciente.observacoes.startswith(demo_service.MARCA_DEMO)


class TestIdempotencia:
    def test_rodar_duas_vezes_nao_duplica(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)
        antes = db.execute(select(func.count()).select_from(Patient)).scalar_one()

        demo_service.semear(db)
        depois = db.execute(select(func.count()).select_from(Patient)).scalar_one()

        assert antes == depois

    def test_limpar_remove_tudo(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)

        demo_service.limpar(db)

        assert db.execute(select(func.count()).select_from(Patient)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(Charge)).scalar_one() == 0
        assert db.execute(select(func.count()).select_from(Booking)).scalar_one() == 0

    def test_limpar_preserva_dado_digitado_a_mao(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """Durante a demonstração cadastramos um paciente ao vivo.

        Regerar o seed não pode apagá-lo.
        """
        from tests.conftest import criar_paciente

        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)
        manual = criar_paciente(db, "Paciente Cadastrado Ao Vivo")
        manual_id = manual.id

        demo_service.limpar(db)

        assert db.get(Patient, manual_id) is not None


class TestDatasRelativas:
    def test_nenhuma_data_fixa_no_futuro_distante(
        self, db: Session, admin: User, recepcao: User, instrutor: User
    ) -> None:
        """As datas são relativas a hoje.

        O seed precisa continuar fazendo sentido no dia da apresentação, seja
        quando for — data fixa no código envelhece.
        """
        _preparar(db, admin, recepcao, instrutor)
        demo_service.semear(db)
        hoje = date.today()

        for matricula in db.execute(select(Enrollment)).scalars():
            idade_em_dias = (hoje - matricula.vigencia_inicio).days
            assert 0 < idade_em_dias < 400, (
                f"matrícula com início implausível: {matricula.vigencia_inicio}"
            )
