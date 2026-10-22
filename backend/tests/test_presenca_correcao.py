"""Corrigir presença e falta direto na agenda.

A recepção marca errado e precisa desfazer. Como presença e falta têm
consequência financeira (saldo do pacote, direito a repor), toda mudança
fica registrada com quem fez e quando.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import AlteracaoPresenca, Booking, OrigemReserva, StatusReserva
from app.models.user import User
from app.services import booking_service, reposicao_service
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_paciente,
    criar_sessao,
    login,
    proxima_segunda,
)


def _reservar(db: Session, instrutor: User, recepcao: User, *, hora: int = 8) -> Booking:
    sessao = criar_sessao(db, instrutor, hora=hora)
    return booking_service.criar(
        db,
        session_id=sessao.id,
        patient_id=criar_paciente(db, f"Paciente {hora}").id,
        criado_por_id=recepcao.id,
    )


def _historico(db: Session, booking_id: int) -> list[AlteracaoPresenca]:
    return list(
        db.execute(
            select(AlteracaoPresenca)
            .where(AlteracaoPresenca.booking_id == booking_id)
            .order_by(AlteracaoPresenca.id)
        ).scalars()
    )


class TestAlternar:
    def test_falta_vira_presenca(self, db: Session, instrutor: User, recepcao: User) -> None:
        reserva = _reservar(db, instrutor, recepcao)
        booking_service.registrar_falta(db, reserva.id, alterado_por_id=recepcao.id)

        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        assert reserva.status is StatusReserva.PRESENTE
        assert reserva.justificada is False

    def test_presenca_vira_falta(self, db: Session, instrutor: User, recepcao: User) -> None:
        reserva = _reservar(db, instrutor, recepcao)
        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        booking_service.registrar_falta(
            db, reserva.id, justificada=True, motivo="Atestado", alterado_por_id=recepcao.id
        )

        assert reserva.status is StatusReserva.FALTA
        assert reserva.justificada is True

    def test_limpar_volta_ao_status_de_antes(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Marcou em quem não devia: volta a confirmada, não a agendada."""
        reserva = _reservar(db, instrutor, recepcao)
        booking_service.confirmar(db, reserva.id)
        booking_service.registrar_falta(db, reserva.id, alterado_por_id=recepcao.id)
        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        booking_service.limpar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        assert reserva.status is StatusReserva.CONFIRMADA

    def test_limpar_sem_registro_e_recusado(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        reserva = _reservar(db, instrutor, recepcao)

        with pytest.raises(HTTPException) as exc:
            booking_service.limpar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        assert exc.value.status_code == 409


class TestHistorico:
    def test_cada_mudanca_registra_quem_e_o_que(
        self, db: Session, instrutor: User, recepcao: User, admin: User
    ) -> None:
        reserva = _reservar(db, instrutor, recepcao)

        booking_service.registrar_falta(db, reserva.id, alterado_por_id=recepcao.id)
        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=admin.id)

        h = _historico(db, reserva.id)
        assert [(x.status_anterior, x.status_novo, x.alterado_por_id) for x in h] == [
            (StatusReserva.AGENDADA, StatusReserva.FALTA, recepcao.id),
            (StatusReserva.FALTA, StatusReserva.PRESENTE, admin.id),
        ]
        assert all(x.alterado_em is not None for x in h)

    def test_registrar_igual_de_novo_nao_duplica(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        reserva = _reservar(db, instrutor, recepcao)

        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=recepcao.id)
        booking_service.registrar_presenca(db, reserva.id, alterado_por_id=recepcao.id)

        assert len(_historico(db, reserva.id)) == 1

    def test_justificar_depois_fica_no_historico(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        reserva = _reservar(db, instrutor, recepcao)

        booking_service.registrar_falta(db, reserva.id, alterado_por_id=recepcao.id)
        booking_service.registrar_falta(
            db, reserva.id, justificada=True, alterado_por_id=recepcao.id
        )

        assert [x.justificada for x in _historico(db, reserva.id)] == [False, True]


class TestFaltaJaReposta:
    """Corrigir a falta não pode deixar uma reposição sem motivo de existir."""

    def _falta_reposta(
        self, db: Session, instrutor: User, recepcao: User
    ) -> tuple[Booking, Booking]:
        criar_configuracao(db)
        falta = _reservar(db, instrutor, recepcao)
        booking_service.registrar_falta(db, falta.id, justificada=True, alterado_por_id=recepcao.id)
        destino = criar_sessao(db, instrutor, hora=10)
        reposicao = booking_service.criar(
            db,
            session_id=destino.id,
            patient_id=falta.patient_id,
            criado_por_id=recepcao.id,
            origem=OrigemReserva.REPOSICAO,
            substitui_booking_id=falta.id,
        )
        return falta, reposicao

    def test_nao_vira_presenca(self, db: Session, instrutor: User, recepcao: User) -> None:
        falta, _ = self._falta_reposta(db, instrutor, recepcao)

        with pytest.raises(HTTPException) as exc:
            booking_service.registrar_presenca(db, falta.id, alterado_por_id=recepcao.id)

        assert exc.value.status_code == 409
        assert "já foi reposta" in exc.value.detail
        assert falta.status is StatusReserva.FALTA

    def test_nao_perde_a_justificativa(self, db: Session, instrutor: User, recepcao: User) -> None:
        falta, _ = self._falta_reposta(db, instrutor, recepcao)

        with pytest.raises(HTTPException):
            booking_service.registrar_falta(
                db, falta.id, justificada=False, alterado_por_id=recepcao.id
            )

        assert falta.justificada is True

    def test_nao_e_limpa(self, db: Session, instrutor: User, recepcao: User) -> None:
        falta, _ = self._falta_reposta(db, instrutor, recepcao)

        with pytest.raises(HTTPException):
            booking_service.limpar_presenca(db, falta.id, alterado_por_id=recepcao.id)

    def test_pode_atualizar_o_motivo(self, db: Session, instrutor: User, recepcao: User) -> None:
        falta, _ = self._falta_reposta(db, instrutor, recepcao)

        booking_service.registrar_falta(
            db, falta.id, justificada=True, motivo="Atestado", alterado_por_id=recepcao.id
        )

        assert falta.motivo_justificativa == "Atestado"

    def test_cancelando_a_reposicao_a_correcao_e_liberada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        falta, reposicao = self._falta_reposta(db, instrutor, recepcao)
        booking_service.cancelar(db, reposicao.id)

        booking_service.registrar_presenca(db, falta.id, alterado_por_id=recepcao.id)

        assert falta.status is StatusReserva.PRESENTE
        assert reposicao_service.listar_pendentes(db) == []


class TestApi:
    def test_grade_mostra_quem_registrou(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        reserva = _reservar(db, instrutor, recepcao)
        t = login(client, recepcao.email)

        r = client.post(f"/api/v1/bookings/{reserva.id}/presenca", headers=auth(t))
        assert r.status_code == 200

        grade = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": proxima_segunda().isoformat()},
            headers=auth(t),
        ).json()
        item = next(rv for s in grade["sessoes"] for rv in s["reservas"] if rv["id"] == reserva.id)
        assert item["presenca_por"] == recepcao.nome
        assert item["presenca_em"] is not None

    def test_limpar_pela_api(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        reserva = _reservar(db, instrutor, recepcao)
        t = login(client, recepcao.email)
        client.post(f"/api/v1/bookings/{reserva.id}/falta", json={}, headers=auth(t))

        r = client.post(f"/api/v1/bookings/{reserva.id}/limpar-presenca", headers=auth(t))

        assert r.status_code == 200
        assert r.json()["status"] == "agendada"

    def test_instrutor_nao_corrige(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Instrutor é somente leitura nesta entrega (CLAUDE.md)."""
        reserva = _reservar(db, instrutor, recepcao)
        t = login(client, instrutor.email)

        r = client.post(f"/api/v1/bookings/{reserva.id}/limpar-presenca", headers=auth(t))

        assert r.status_code == 403
