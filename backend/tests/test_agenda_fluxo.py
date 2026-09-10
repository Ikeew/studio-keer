"""Fluxo de presença, falta e remarcação, e o RBAC da agenda."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking import OrigemReserva, StatusReserva
from app.models.user import User
from app.services import booking_service
from tests.conftest import auth, criar_configuracao, criar_paciente, criar_sessao, login


def _reservar(db: Session, sessao_id: int, nome: str, quem: User) -> int:
    reserva = booking_service.criar(
        db,
        session_id=sessao_id,
        patient_id=criar_paciente(db, nome).id,
        criado_por_id=quem.id,
    )
    return reserva.id


class TestPresenca:
    def test_ciclo_agendada_confirmada_presente(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Ana", recepcao)

        assert booking_service.buscar(db, rid).status is StatusReserva.AGENDADA
        booking_service.confirmar(db, rid)
        assert booking_service.buscar(db, rid).status is StatusReserva.CONFIRMADA
        booking_service.registrar_presenca(db, rid)
        assert booking_service.buscar(db, rid).status is StatusReserva.PRESENTE

    def test_presenca_e_eixo_separado_do_pagamento(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Nunca existe um estado que misture presença e pagamento."""
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Ana", recepcao)
        reserva = booking_service.buscar(db, rid)

        assert set(StatusReserva) == {
            StatusReserva.AGENDADA,
            StatusReserva.CONFIRMADA,
            StatusReserva.PRESENTE,
            StatusReserva.FALTA,
            StatusReserva.CANCELADA,
        }
        assert not hasattr(reserva, "pago")


class TestFalta:
    def test_recepcao_marca_falta_justificada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Quem julga é a RECEPÇÃO — o sistema não infere."""
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Faltou", recepcao)

        reserva = booking_service.registrar_falta(
            db, rid, justificada=True, motivo="Atestado médico"
        )

        assert reserva.status is StatusReserva.FALTA
        assert reserva.justificada is True
        assert reserva.motivo_justificativa == "Atestado médico"

    def test_falta_nao_justificada(self, db: Session, instrutor: User, recepcao: User) -> None:
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Sumiu", recepcao)

        reserva = booking_service.registrar_falta(db, rid)

        assert reserva.justificada is False

    def test_nao_ha_prazo_que_transforme_cancelamento_em_falta(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A regra das 24h era premissa do time, descartada (P4).

        Cancelar NUNCA vira falta sozinho, por mais em cima da hora que seja.
        """
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Cancelou", recepcao)

        reserva = booking_service.cancelar(db, rid, motivo="Avisou agora")

        assert reserva.status is StatusReserva.CANCELADA
        assert reserva.status is not StatusReserva.FALTA
        assert reserva.justificada is False

    def test_configuracao_nao_tem_prazo_de_cancelamento(self, db: Session) -> None:
        """Guarda contra alguém reintroduzir o prazo sem querer."""
        from app.models.configuracao import Configuracao

        assert not hasattr(Configuracao, "cancelamento_antecedencia_horas")

    def test_cancelada_nao_recebe_falta(self, db: Session, instrutor: User, recepcao: User) -> None:
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Cancelou", recepcao)
        booking_service.cancelar(db, rid)

        with pytest.raises(HTTPException) as exc:
            booking_service.registrar_falta(db, rid)

        assert exc.value.status_code == 409

    def test_presenca_registrada_nao_pode_ser_cancelada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Veio", recepcao)
        booking_service.registrar_presenca(db, rid)

        with pytest.raises(HTTPException) as exc:
            booking_service.cancelar(db, rid)

        assert exc.value.status_code == 409


class TestRemarcacao:
    def test_remarcar_mantem_o_vinculo_de_origem(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        origem = criar_sessao(db, instrutor, hora=8)
        destino = criar_sessao(db, instrutor, hora=9)
        rid = _reservar(db, origem.id, "Mudou", recepcao)

        nova = booking_service.remarcar(
            db, rid, nova_session_id=destino.id, criado_por_id=recepcao.id
        )

        assert nova.substitui_booking_id == rid
        assert nova.origem is OrigemReserva.REMARCACAO
        assert nova.session_id == destino.id

    def test_remarcar_libera_a_vaga_de_origem(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        origem = criar_sessao(db, instrutor, hora=8, capacidade=1)
        destino = criar_sessao(db, instrutor, hora=9, capacidade=1)
        rid = _reservar(db, origem.id, "Mudou", recepcao)

        booking_service.remarcar(db, rid, nova_session_id=destino.id, criado_por_id=recepcao.id)

        assert booking_service.vagas_livres(db, origem) == 1
        assert booking_service.buscar(db, rid).status is StatusReserva.CANCELADA

    def test_remarcar_para_turma_cheia_e_recusado(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Remarcar não é atalho para furar turma cheia."""
        criar_configuracao(db)
        origem = criar_sessao(db, instrutor, hora=8)
        destino = criar_sessao(db, instrutor, hora=9, capacidade=1)
        _reservar(db, destino.id, "Ja Ocupa", recepcao)
        rid = _reservar(db, origem.id, "Quer Mudar", recepcao)

        with pytest.raises(HTTPException) as exc:
            booking_service.remarcar(db, rid, nova_session_id=destino.id, criado_por_id=recepcao.id)

        assert exc.value.status_code == 409

    def test_reserva_original_sobrevive_se_o_destino_estiver_cheio(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """O paciente não pode ficar sem nenhuma das duas vagas."""
        criar_configuracao(db)
        origem = criar_sessao(db, instrutor, hora=8)
        destino = criar_sessao(db, instrutor, hora=9, capacidade=1)
        _reservar(db, destino.id, "Ja Ocupa", recepcao)
        rid = _reservar(db, origem.id, "Quer Mudar", recepcao)

        with pytest.raises(HTTPException):
            booking_service.remarcar(db, rid, nova_session_id=destino.id, criado_por_id=recepcao.id)

        assert booking_service.buscar(db, rid).status is StatusReserva.AGENDADA

    def test_uma_falta_gera_uma_reposicao_so(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Repor duas vezes a mesma falta seria overbooking por outra porta."""
        from sqlalchemy.exc import IntegrityError

        from app.models.booking import Booking

        criar_configuracao(db)
        origem = criar_sessao(db, instrutor, hora=8)
        d1 = criar_sessao(db, instrutor, hora=9)
        rid = _reservar(db, origem.id, "Faltou", recepcao)
        booking_service.registrar_falta(db, rid, justificada=True)

        paciente_id = booking_service.buscar(db, rid).patient_id
        booking_service.criar(
            db,
            session_id=d1.id,
            patient_id=paciente_id,
            criado_por_id=recepcao.id,
            origem=OrigemReserva.REPOSICAO,
            substitui_booking_id=rid,
        )

        d2 = criar_sessao(db, instrutor, hora=10)
        db.add(
            Booking(
                session_id=d2.id,
                patient_id=paciente_id,
                posicao=1,
                capacidade_sessao=4,
                origem=OrigemReserva.REPOSICAO,
                status=StatusReserva.AGENDADA,
                substitui_booking_id=rid,  # a MESMA falta
                criado_por_id=recepcao.id,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()


class TestCancelarTurma:
    def test_cancelar_sessao_cancela_as_reservas(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        from app.services import session_service

        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Aluno", recepcao)

        session_service.cancelar(db, sessao.id, motivo="Instrutora doente")

        assert booking_service.buscar(db, rid).status is StatusReserva.CANCELADA

    def test_sessao_cancelada_nao_aceita_reserva(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        from app.services import session_service

        sessao = criar_sessao(db, instrutor)
        session_service.cancelar(db, sessao.id)

        with pytest.raises(HTTPException) as exc:
            _reservar(db, sessao.id, "Tarde Demais", recepcao)

        assert exc.value.status_code == 409


class TestRbacDaAgenda:
    def test_instrutor_le_a_agenda(self, client: TestClient, db: Session, instrutor: User) -> None:
        """É a única tela dele — leitura precisa funcionar."""
        criar_configuracao(db)
        t = login(client, instrutor.email)

        r = client.get("/api/v1/agenda/semana", headers=auth(t))

        assert r.status_code == 200

    def test_instrutor_nao_escreve_nada(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Somente leitura nesta entrega. Quem registra é a recepção."""
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor)
        rid = _reservar(db, sessao.id, "Aluno", recepcao)
        t = login(client, instrutor.email)

        assert (
            client.post(
                "/api/v1/bookings",
                json={"session_id": sessao.id, "patient_id": 1},
                headers=auth(t),
            ).status_code
            == 403
        )
        assert client.post(f"/api/v1/bookings/{rid}/presenca", headers=auth(t)).status_code == 403
        assert (
            client.post(
                f"/api/v1/bookings/{rid}/falta", json={"justificada": True}, headers=auth(t)
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/api/v1/bookings/{rid}/cancelar", json={"motivo": "x"}, headers=auth(t)
            ).status_code
            == 403
        )

    def test_recepcao_escreve(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor)
        paciente = criar_paciente(db, "Novo")
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/bookings",
            json={"session_id": sessao.id, "patient_id": paciente.id},
            headers=auth(t),
        )

        assert r.status_code == 201

    def test_turma_cheia_devolve_409_e_nao_500(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A recepção precisa entender o erro, não ver uma tela quebrada."""
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=1)
        t = login(client, recepcao.email)
        client.post(
            "/api/v1/bookings",
            json={"session_id": sessao.id, "patient_id": criar_paciente(db, "A").id},
            headers=auth(t),
        )

        r = client.post(
            "/api/v1/bookings",
            json={"session_id": sessao.id, "patient_id": criar_paciente(db, "B").id},
            headers=auth(t),
        )

        assert r.status_code == 409
        assert "completa" in r.json()["detail"]

    def test_sem_token_e_401(self, client: TestClient) -> None:
        assert client.get("/api/v1/agenda/semana").status_code == 401
