"""Indicadores do dashboard, com atenção à taxa de ocupação.

A taxa é o número que a banca vai perguntar, então a fórmula está testada
caso a caso — cada status de reserva contribuindo (ou não) do jeito certo.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import booking_service, dashboard_service
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_paciente,
    criar_servico,
    criar_sessao,
    login,
)


def _hoje_util() -> date:
    """Um dia desta semana em que o studio atende (nunca domingo)."""
    hoje = date.today()
    return hoje if hoje.weekday() != 6 else hoje + timedelta(days=1)


class TestTaxaDeOcupacao:
    """taxa = reservas ativas ÷ capacidade ofertada."""

    def test_sem_sessao_a_taxa_e_zero_e_nao_indefinida(self, db: Session) -> None:
        criar_configuracao(db)
        hoje = date.today()

        t = dashboard_service.taxa_de_ocupacao(db, hoje, hoje)

        assert t.capacidade_ofertada == 0
        assert t.percentual == 0

    def test_turma_cheia_e_cem_por_cento(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        dia = _hoje_util()
        sessao = criar_sessao(db, instrutor, dia=dia, capacidade=4)
        for i in range(4):
            booking_service.criar(
                db,
                session_id=sessao.id,
                patient_id=criar_paciente(db, f"P{i}").id,
                criado_por_id=recepcao.id,
            )

        t = dashboard_service.taxa_de_ocupacao(db, dia, dia)

        assert t.reservas_ativas == 4
        assert t.capacidade_ofertada == 4
        assert t.percentual == 100

    def test_metade_da_turma_e_cinquenta_por_cento(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        dia = _hoje_util()
        sessao = criar_sessao(db, instrutor, dia=dia, capacidade=4)
        for i in range(2):
            booking_service.criar(
                db,
                session_id=sessao.id,
                patient_id=criar_paciente(db, f"M{i}").id,
                criado_por_id=recepcao.id,
            )

        assert dashboard_service.taxa_de_ocupacao(db, dia, dia).percentual == 50

    def test_cancelada_nao_conta(self, db: Session, instrutor: User, recepcao: User) -> None:
        """A vaga voltou ao pool. Contá-la inflaria a taxa com lugar vazio."""
        criar_configuracao(db)
        dia = _hoje_util()
        sessao = criar_sessao(db, instrutor, dia=dia, capacidade=4)
        reserva = booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "Cancelou").id,
            criado_por_id=recepcao.id,
        )
        booking_service.cancelar(db, reserva.id)

        t = dashboard_service.taxa_de_ocupacao(db, dia, dia)

        assert t.reservas_ativas == 0
        assert t.percentual == 0

    def test_falta_conta(self, db: Session, instrutor: User, recepcao: User) -> None:
        """O lugar ficou reservado e ninguém mais pôde usá-lo.

        A taxa mede OCUPAÇÃO, não comparecimento.
        """
        criar_configuracao(db)
        dia = _hoje_util()
        sessao = criar_sessao(db, instrutor, dia=dia, capacidade=4)
        reserva = booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "Faltou").id,
            criado_por_id=recepcao.id,
        )
        booking_service.registrar_falta(db, reserva.id, justificada=True)

        t = dashboard_service.taxa_de_ocupacao(db, dia, dia)

        assert t.reservas_ativas == 1
        assert t.percentual == 25

    def test_presente_e_confirmada_contam(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        dia = _hoje_util()
        sessao = criar_sessao(db, instrutor, dia=dia, capacidade=4)
        a = booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "A").id,
            criado_por_id=recepcao.id,
        )
        b = booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "B").id,
            criado_por_id=recepcao.id,
        )
        booking_service.registrar_presenca(db, a.id)
        booking_service.confirmar(db, b.id)

        assert dashboard_service.taxa_de_ocupacao(db, dia, dia).reservas_ativas == 2

    def test_usa_a_capacidade_da_sessao_e_nao_a_do_servico(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Uma sessão pode ter override de capacidade."""
        criar_configuracao(db)
        dia = _hoje_util()
        servico = criar_servico(db, nome="Override", capacidade=4)
        sessao = criar_sessao(db, instrutor, servico=servico, dia=dia, capacidade=2)
        booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "Um").id,
            criado_por_id=recepcao.id,
        )

        t = dashboard_service.taxa_de_ocupacao(db, dia, dia)

        assert t.capacidade_ofertada == 2, "usou a capacidade do serviço, não da sessão"
        assert t.percentual == 50

    def test_sessao_cancelada_sai_do_denominador(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        from app.services import session_service

        criar_configuracao(db)
        dia = _hoje_util()
        viva = criar_sessao(db, instrutor, dia=dia, hora=8, capacidade=4)
        morta = criar_sessao(db, instrutor, dia=dia, hora=9, capacidade=4)
        booking_service.criar(
            db,
            session_id=viva.id,
            patient_id=criar_paciente(db, "Viva").id,
            criado_por_id=recepcao.id,
        )
        session_service.cancelar(db, morta.id, motivo="Instrutora doente")

        t = dashboard_service.taxa_de_ocupacao(db, dia, dia)

        assert t.capacidade_ofertada == 4, "turma cancelada não oferece capacidade"
        assert t.percentual == 25

    def test_numerador_e_denominador_sao_expostos(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """Percentual sozinho não é auditável."""
        criar_configuracao(db)
        t = login(client, recepcao.email)

        r = client.get("/api/v1/dashboard", headers=auth(t))

        oc = r.json()["ocupacao"]
        assert "reservas_ativas" in oc and "capacidade_ofertada" in oc
        assert "cancelada não conta" in oc["formula"]


class TestIndicadores:
    def test_agendamentos_hoje_conta_so_hoje(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        hoje = _hoje_util()
        hoje_s = criar_sessao(db, instrutor, dia=hoje, hora=8)
        outro = criar_sessao(db, instrutor, dia=hoje + timedelta(days=7), hora=8)
        for s in (hoje_s, outro):
            booking_service.criar(
                db,
                session_id=s.id,
                patient_id=criar_paciente(db, f"P{s.id}").id,
                criado_por_id=recepcao.id,
            )

        i = dashboard_service.indicadores(db)

        if date.today() == hoje:
            assert i.agendamentos_hoje == 1

    def test_pacientes_ativos_ignora_inativos(self, db: Session, recepcao: User) -> None:
        criar_configuracao(db)
        criar_paciente(db, "Ativo Um")
        inativo = criar_paciente(db, "Inativo")
        inativo.ativo = False
        db.flush()

        assert dashboard_service.indicadores(db).pacientes_ativos == 1

    def test_proximos_agendamentos_ordenados_por_hora(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        hoje = date.today()
        if hoje.weekday() == 6:
            return
        for hora in (10, 8, 9):
            s = criar_sessao(db, instrutor, dia=hoje, hora=hora)
            booking_service.criar(
                db,
                session_id=s.id,
                patient_id=criar_paciente(db, f"H{hora}").id,
                criado_por_id=recepcao.id,
            )

        horas = [p.hora for p in dashboard_service.indicadores(db).proximos]

        assert horas == sorted(horas)

    def test_proximos_ignora_cancelada(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        hoje = date.today()
        if hoje.weekday() == 6:
            return
        s = criar_sessao(db, instrutor, dia=hoje)
        reserva = booking_service.criar(
            db,
            session_id=s.id,
            patient_id=criar_paciente(db, "Cancelou").id,
            criado_por_id=recepcao.id,
        )
        booking_service.cancelar(db, reserva.id)

        assert dashboard_service.indicadores(db).proximos == []


class TestAgendaDoInstrutor:
    def test_mostra_so_as_aulas_dele(
        self, db: Session, instrutor: User, admin: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        hoje = date.today()
        if hoje.weekday() == 6:
            return
        minha = criar_sessao(db, instrutor, dia=hoje, hora=8)
        outra = criar_sessao(db, admin, dia=hoje, hora=9)
        for s in (minha, outra):
            booking_service.criar(
                db,
                session_id=s.id,
                patient_id=criar_paciente(db, f"S{s.id}").id,
                criado_por_id=recepcao.id,
            )

        aulas = dashboard_service.agenda_do_instrutor(db, instrutor.id)

        assert len(aulas) == 1
        assert aulas[0].instrutor_nome == instrutor.nome

    def test_instrutor_nao_le_a_agenda_de_outro(
        self, client: TestClient, db: Session, instrutor: User, admin: User, recepcao: User
    ) -> None:
        """A rota filtra pelo usuário do TOKEN, não por id na URL.

        Passar `professional_id` de outra pessoa é ignorado: não existe
        caminho para um instrutor ler a agenda de outro.
        """
        criar_configuracao(db)
        hoje = date.today()
        if hoje.weekday() == 6:
            return
        do_admin = criar_sessao(db, admin, dia=hoje, hora=9)
        booking_service.criar(
            db,
            session_id=do_admin.id,
            patient_id=criar_paciente(db, "Aluno do Admin").id,
            criado_por_id=recepcao.id,
        )
        db.commit()
        t = login(client, instrutor.email)

        r = client.get(
            "/api/v1/dashboard/minha-agenda",
            params={"professional_id": admin.id},
            headers=auth(t),
        )

        assert r.status_code == 200
        assert r.json() == [], "o instrutor não tem aula hoje; o id na URL foi ignorado"


class TestRbacDoDashboard:
    def test_instrutor_nao_ve_o_dashboard_de_gestao(
        self, client: TestClient, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, instrutor.email)

        assert client.get("/api/v1/dashboard", headers=auth(t)).status_code == 403
        assert client.get("/api/v1/dashboard/servicos", headers=auth(t)).status_code == 403

    def test_recepcao_e_admin_veem(
        self, client: TestClient, db: Session, admin: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        for user in (admin, recepcao):
            t = login(client, user.email)
            assert client.get("/api/v1/dashboard", headers=auth(t)).status_code == 200

    def test_recepcao_nao_acessa_minha_agenda(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """A recepção usa a grade completa, não a visão de um instrutor."""
        criar_configuracao(db)
        t = login(client, recepcao.email)

        assert client.get("/api/v1/dashboard/minha-agenda", headers=auth(t)).status_code == 403


class TestEstatisticasDeServicos:
    def test_conta_por_servico(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        hoje = _hoje_util()
        pilates = criar_servico(db, nome="Pilates Stat", capacidade=4)
        sessao = criar_sessao(db, instrutor, servico=pilates, dia=hoje, capacidade=4)
        for i in range(2):
            booking_service.criar(
                db,
                session_id=sessao.id,
                patient_id=criar_paciente(db, f"E{i}").id,
                criado_por_id=recepcao.id,
            )

        stats = {s.nome: s for s in dashboard_service.estatisticas_de_servicos(db)}

        assert stats["Pilates Stat"].sessoes_no_mes == 1
        assert stats["Pilates Stat"].reservas_no_mes == 2
        assert stats["Pilates Stat"].ocupacao_percentual == 50

    def test_servico_sem_sessao_aparece_zerado(self, db: Session, recepcao: User) -> None:
        criar_configuracao(db)
        criar_servico(db, nome="Sem Movimento")

        stats = {s.nome: s for s in dashboard_service.estatisticas_de_servicos(db)}

        assert stats["Sem Movimento"].sessoes_no_mes == 0
        assert stats["Sem Movimento"].ocupacao_percentual == 0
