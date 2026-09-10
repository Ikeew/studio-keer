"""A grade não pode oferecer o que não existe."""

from datetime import date, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import booking_service, schedule_service, session_service
from app.services.schedule_service import FUSO
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_paciente,
    criar_servico,
    criar_sessao,
    login,
    proxima_segunda,
)


class TestJanelaDeFuncionamento:
    def test_pausa_nao_aparece_na_grade(self, db: Session) -> None:
        """12:00 e 13:00 não existem. Confirmado pela cliente (P6)."""
        criar_configuracao(db)

        janelas = schedule_service.janela_da_semana(db, proxima_segunda())
        segunda = janelas[0]

        horas = [h.hour for h in segunda.horas]
        assert 11 in horas
        assert 12 not in horas, "12:00 está na pausa"
        assert 13 not in horas, "13:00 está na pausa"
        assert 14 in horas

    def test_fora_da_janela_nao_aparece(self, db: Session) -> None:
        criar_configuracao(db)

        segunda = schedule_service.janela_da_semana(db, proxima_segunda())[0]

        horas = [h.hour for h in segunda.horas]
        assert min(horas) == 6, "abre às 06:00"
        assert max(horas) == 20, "última turma começa às 20:00 e fecha às 21:00"

    def test_sabado_aberto_e_domingo_fechado(self, db: Session) -> None:
        """Sábado foi confirmado pela cliente (P6)."""
        criar_configuracao(db)

        janelas = schedule_service.janela_da_semana(db, proxima_segunda())
        sabado = janelas[5]
        domingo = janelas[6]

        assert sabado.aberto and len(sabado.horas) > 0
        assert not domingo.aberto and sabado.dia.weekday() == 5
        assert domingo.horas == ()

    def test_sabado_tem_a_mesma_pausa_dos_dias_uteis(self, db: Session) -> None:
        criar_configuracao(db)

        janelas = schedule_service.janela_da_semana(db, proxima_segunda())

        assert [h.hour for h in janelas[0].horas] == [h.hour for h in janelas[5].horas]


class TestCriarSessao:
    def test_recusa_turma_dentro_da_pausa(self, db: Session, instrutor: User) -> None:
        """Dado que existe e não aparece é pior que dado recusado."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Pausa")

        with pytest.raises(HTTPException) as exc:
            session_service.criar(
                db,
                service_id=servico.id,
                professional_id=instrutor.id,
                inicia_em=datetime.combine(proxima_segunda(), time(13, 0), tzinfo=FUSO),
            )

        assert exc.value.status_code == 400
        assert "não atende" in exc.value.detail

    def test_recusa_turma_no_domingo(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Domingo")
        domingo = proxima_segunda() + timedelta(days=6)

        with pytest.raises(HTTPException) as exc:
            session_service.criar(
                db,
                service_id=servico.id,
                professional_id=instrutor.id,
                inicia_em=datetime.combine(domingo, time(9, 0), tzinfo=FUSO),
            )

        assert exc.value.status_code == 400

    def test_recusa_turma_antes_da_abertura(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Madrugada")

        with pytest.raises(HTTPException) as exc:
            session_service.criar(
                db,
                service_id=servico.id,
                professional_id=instrutor.id,
                inicia_em=datetime.combine(proxima_segunda(), time(5, 0), tzinfo=FUSO),
            )

        assert exc.value.status_code == 400

    def test_aceita_horario_valido_e_herda_capacidade(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates OK", capacidade=4)

        sessao = session_service.criar(
            db,
            service_id=servico.id,
            professional_id=instrutor.id,
            inicia_em=datetime.combine(proxima_segunda(), time(8, 0), tzinfo=FUSO),
        )

        assert sessao.capacidade == 4
        assert sessao.termina_em - sessao.inicia_em == timedelta(minutes=60)

    def test_instrutor_nao_ministra_duas_turmas_no_mesmo_horario(
        self, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        quando = datetime.combine(proxima_segunda(), time(8, 0), tzinfo=FUSO)
        session_service.criar(
            db,
            service_id=criar_servico(db, nome="A").id,
            professional_id=instrutor.id,
            inicia_em=quando,
        )

        with pytest.raises(HTTPException) as exc:
            session_service.criar(
                db,
                service_id=criar_servico(db, nome="B").id,
                professional_id=instrutor.id,
                inicia_em=quando,
            )

        assert exc.value.status_code == 409


class TestArmadilhaDaMaterializacao:
    """Só sessão que EXISTE é oferecida.

    Se a disponibilidade viesse da grade teórica de horários, um horário ainda
    não materializado pareceria vago, receberia uma reposição, e depois seria
    preenchido pelo gerador de recorrência da Fase 4 — recriando o overbooking
    pelo caminho oposto ao que estamos evitando.
    """

    def test_horario_sem_turma_nao_e_oferecido_como_vaga(
        self, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        segunda = proxima_segunda()
        # A grade teórica tem 06:00 às 20:00 em seis dias — dezenas de
        # horários. Nenhuma sessão foi materializada.

        vagas = schedule_service.sessoes_com_vaga(db, de=segunda, ate=segunda + timedelta(days=6))

        assert vagas == [], "horário sem turma materializada não pode aparecer como vaga livre"

    def test_sessao_materializada_com_reservas_conta_a_ocupacao(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A consulta enxerga as reservas que a sessão JÁ tem.

        É o contrato com a Fase 4: o gerador materializa antes, com as
        reservas recorrentes dentro, e a disponibilidade lê o estado real.
        """
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=4)
        for i in range(3):
            booking_service.criar(
                db,
                session_id=sessao.id,
                patient_id=criar_paciente(db, f"Fixo {i}").id,
                criado_por_id=recepcao.id,
            )

        dia = sessao.inicia_em.astimezone(FUSO).date()
        vagas = schedule_service.sessoes_com_vaga(db, de=dia, ate=dia)

        assert len(vagas) == 1
        assert vagas[0].ocupadas == 3
        assert vagas[0].sessao.capacidade - vagas[0].ocupadas == 1

    def test_turma_cheia_some_da_lista_de_vagas(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A tela precisa poder dizer 'não há vaga' ANTES de oferecer."""
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=2)
        for i in range(2):
            booking_service.criar(
                db,
                session_id=sessao.id,
                patient_id=criar_paciente(db, f"Cheio {i}").id,
                criado_por_id=recepcao.id,
            )

        dia = sessao.inicia_em.astimezone(FUSO).date()
        vagas = schedule_service.sessoes_com_vaga(db, de=dia, ate=dia)

        assert vagas == []

    def test_nao_oferece_horario_em_que_o_paciente_ja_esta(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=4)
        paciente = criar_paciente(db, "Ja Marcado")
        booking_service.criar(
            db, session_id=sessao.id, patient_id=paciente.id, criado_por_id=recepcao.id
        )

        dia = sessao.inicia_em.astimezone(FUSO).date()
        vagas = schedule_service.sessoes_com_vaga(
            db, de=dia, ate=dia, excluir_patient_id=paciente.id
        )

        assert vagas == []


class TestGradeViaApi:
    def test_grade_devolve_horarios_sem_a_pausa(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, recepcao.email)

        r = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": proxima_segunda().isoformat()},
            headers=auth(t),
        )

        assert r.status_code == 200
        segunda = r.json()["dias"][0]
        assert "12:00" not in segunda["horas"]
        assert "13:00" not in segunda["horas"]
        assert "11:00" in segunda["horas"] and "14:00" in segunda["horas"]

    def test_grade_traz_instrutor_e_ocupacao(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Os prints omitem o instrutor, mas a interface tem de mostrá-lo."""
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=4)
        booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "Maria Silva").id,
            criado_por_id=recepcao.id,
        )
        t = login(client, recepcao.email)

        r = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": proxima_segunda().isoformat()},
            headers=auth(t),
        )

        sessoes = r.json()["sessoes"]
        assert len(sessoes) == 1
        assert sessoes[0]["instrutor_nome"] == instrutor.nome
        assert sessoes[0]["ocupadas"] == 1
        assert sessoes[0]["vagas"] == 3
        assert sessoes[0]["lotada"] is False
        assert sessoes[0]["reservas"][0]["paciente_nome"] == "Maria Silva"

    def test_grade_marca_turma_lotada(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=1)
        booking_service.criar(
            db,
            session_id=sessao.id,
            patient_id=criar_paciente(db, "Cheia").id,
            criado_por_id=recepcao.id,
        )
        t = login(client, recepcao.email)

        r = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": proxima_segunda().isoformat()},
            headers=auth(t),
        )

        assert r.json()["sessoes"][0]["lotada"] is True
        assert r.json()["sessoes"][0]["vagas"] == 0

    def test_semana_comeca_na_segunda(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, recepcao.email)
        quarta = proxima_segunda() + timedelta(days=2)

        r = client.get(
            "/api/v1/agenda/semana", params={"referencia": quarta.isoformat()}, headers=auth(t)
        )

        assert date.fromisoformat(r.json()["inicio"]) == proxima_segunda()


class TestFusoHorario:
    """Regressão: datetime sem fuso é horário do STUDIO, não do servidor.

    Encontrado rodando o sistema em container (servidor em UTC), não nos
    testes — eles construíam o datetime já com fuso. Sem a conversão, 08:00
    virava 05:00 e era recusado, e 13:00 virava 10:00 e criava turma DENTRO
    da pausa.
    """

    def test_hora_sem_fuso_e_interpretada_como_do_studio(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Fuso Valido")
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/sessions",
            json={
                "service_id": servico.id,
                "professional_id": instrutor.id,
                # Sem sufixo de fuso, como o formulário envia.
                "inicia_em": f"{proxima_segunda()}T08:00:00",
            },
            headers=auth(t),
        )

        assert r.status_code == 201, r.text
        assert r.json()["hora"] == "08:00"

    def test_hora_sem_fuso_dentro_da_pausa_e_recusada(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """O caso que o bug deixava passar."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Fuso Pausa")
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/sessions",
            json={
                "service_id": servico.id,
                "professional_id": instrutor.id,
                "inicia_em": f"{proxima_segunda()}T13:00:00",
            },
            headers=auth(t),
        )

        assert r.status_code == 400
        assert "não atende" in r.json()["detail"]
