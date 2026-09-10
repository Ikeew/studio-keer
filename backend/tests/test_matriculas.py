"""Matrículas: capacidade na venda, idempotência do gerador, encerramento."""

from datetime import date, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.enrollment import StatusMatricula
from app.models.session import Session as Sessao
from app.models.user import User
from app.services import booking_service, enrollment_service
from tests.conftest import (
    criar_configuracao,
    criar_matricula,
    criar_paciente,
    criar_servico,
)

SEGUNDA, TERCA = 1, 2


class TestCapacidadeNaVendaDoHorario:
    """PONTO 2 DA CAPACIDADE — onde nasce o overbooking vendido no balcão.

    Se cinco pessoas têm horário fixo às segundas 08:00 e a capacidade é 4,
    TODA ocorrência nasce lotada e nenhuma reposição está envolvida.
    """

    def test_quatro_matriculas_cabem_no_horario(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Cap", capacidade=4)

        for i in range(4):
            criar_matricula(db, criar_paciente(db, f"Fixo {i}"), instrutor, servico)

        ativas = enrollment_service._matriculas_ativas_no_slot(
            db, service_id=servico.id, dia_semana=SEGUNDA, hora=time(8, 0)
        )
        assert len(ativas) == 4

    def test_a_quinta_matricula_e_recusada(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Quinta", capacidade=4)
        for i in range(4):
            criar_matricula(db, criar_paciente(db, f"Fixo {i}"), instrutor, servico)

        with pytest.raises(HTTPException) as exc:
            criar_matricula(db, criar_paciente(db, "Quinto"), instrutor, servico)

        assert exc.value.status_code == 409

    def test_a_mensagem_explica_que_o_problema_e_o_horario(
        self, db: Session, instrutor: User
    ) -> None:
        """Quem lê precisa entender que não adianta tentar de novo amanhã."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Msg", capacidade=1)
        criar_matricula(db, criar_paciente(db, "Primeiro"), instrutor, servico)

        with pytest.raises(HTTPException) as exc:
            criar_matricula(db, criar_paciente(db, "Segundo"), instrutor, servico)

        detalhe = exc.value.detail
        assert "segunda" in detalhe and "08:00" in detalhe
        assert "é o horário" in detalhe
        assert "alunos fixos" in detalhe

    def test_horarios_diferentes_nao_competem(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Slots", capacidade=1)
        criar_matricula(db, criar_paciente(db, "Segunda"), instrutor, servico)

        outro = criar_matricula(
            db,
            criar_paciente(db, "Terça"),
            instrutor,
            servico,
            horarios=[(TERCA, time(8, 0))],
        )

        assert outro.id is not None

    def test_matricula_encerrada_libera_o_horario(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Libera", capacidade=1)
        primeira = criar_matricula(db, criar_paciente(db, "Saiu"), instrutor, servico)

        enrollment_service.encerrar(db, primeira.id)
        nova = criar_matricula(db, criar_paciente(db, "Entrou"), instrutor, servico)

        assert nova.id is not None

    def test_matricula_em_horario_de_pausa_e_recusada(self, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Pausa Mat")

        with pytest.raises(HTTPException) as exc:
            criar_matricula(
                db,
                criar_paciente(db, "Pausa"),
                instrutor,
                servico,
                horarios=[(SEGUNDA, time(13, 0))],
            )

        assert exc.value.status_code == 400

    def test_frequencia_e_derivada_da_contagem(self, db: Session, instrutor: User) -> None:
        """Nunca um campo: campo poderia discordar das linhas."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates 2x")

        matricula = criar_matricula(
            db,
            criar_paciente(db, "Duas Vezes"),
            instrutor,
            servico,
            horarios=[(SEGUNDA, time(8, 0)), (3, time(8, 0))],
        )

        assert enrollment_service.frequencia_semanal(matricula) == 2
        assert not hasattr(matricula, "frequencia")


class TestGeradorIdempotente:
    def _contar(self, db: Session) -> tuple[int, int]:
        sessoes = db.execute(select(func.count()).select_from(Sessao)).scalar_one()
        reservas = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(Booking.status != StatusReserva.CANCELADA)
        ).scalar_one()
        return sessoes, reservas

    def test_gera_a_grade_do_horizonte(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Gerar")
        criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)

        r = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        assert r.sessoes_criadas > 0
        assert r.reservas_criadas == r.sessoes_criadas
        # 8 semanas de horizonte, um horário por semana.
        assert 7 <= r.reservas_criadas <= 9

    def test_rodar_duas_vezes_nao_duplica(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Idem")
        criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)

        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)
        antes = self._contar(db)
        segunda = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)
        depois = self._contar(db)

        assert antes == depois, "a segunda execução não pode criar nada"
        assert segunda.sessoes_criadas == 0
        assert segunda.reservas_criadas == 0
        assert segunda.reservas_ja_existentes > 0

    def test_execucao_interrompida_no_meio_pode_ser_repetida(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Simula queda no meio: parte da grade existe, o resto não.

        Repetir tem de completar sem limpeza e sem duplicar o que já estava.
        """
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Parcial")
        criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)

        # Gera só 3 semanas — como se tivesse morrido no meio.
        parcial = enrollment_service.gerar_grade(
            db, criado_por_id=recepcao.id, ate=date.today() + timedelta(weeks=3)
        )
        assert parcial.reservas_criadas > 0
        sessoes_parciais, reservas_parciais = self._contar(db)

        completa = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)
        _, reservas_finais = self._contar(db)

        assert completa.reservas_ja_existentes == reservas_parciais, (
            "as reservas da execução interrompida devem ser reconhecidas"
        )
        assert completa.sessoes_reaproveitadas == sessoes_parciais
        assert reservas_finais > reservas_parciais, "o resto deve ter sido gerado"

    def test_gerador_nao_fura_a_capacidade(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Turma cheia por avulsas: o gerador REPORTA, não força."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Cheio", capacidade=1)
        matricula = criar_matricula(db, criar_paciente(db, "Fixo"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        # Cancela a reserva recorrente e ocupa a vaga com uma avulsa.
        primeira = db.execute(
            select(Booking).where(Booking.enrollment_id == matricula.id).limit(1)
        ).scalar_one()
        sessao_id = primeira.session_id
        booking_service.cancelar(db, primeira.id)
        booking_service.criar(
            db,
            session_id=sessao_id,
            patient_id=criar_paciente(db, "Avulso").id,
            criado_por_id=recepcao.id,
        )

        r = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        assert len(r.sem_vaga) == 1, "o conflito é reportado, não silenciado"
        sessao = db.get(Sessao, sessao_id)
        assert sessao is not None
        assert booking_service.vagas_livres(db, sessao) == 0

    def test_reserva_recorrente_aponta_para_a_matricula(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Link")
        matricula = criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)

        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        reserva = db.execute(
            select(Booking).where(Booking.enrollment_id == matricula.id).limit(1)
        ).scalar_one()
        assert reserva.origem is OrigemReserva.RECORRENTE
        assert reserva.package_id is None


class TestEncerramentoESuspensao:
    def test_encerrar_libera_reservas_futuras(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Encerra")
        matricula = criar_matricula(db, criar_paciente(db, "Sai"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        liberadas = enrollment_service.encerrar(db, matricula.id, motivo="Mudou de cidade")

        assert liberadas > 0
        ativas = db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.enrollment_id == matricula.id,
                Booking.status != StatusReserva.CANCELADA,
            )
        ).scalar_one()
        assert ativas == 0

    def test_presenca_registrada_nao_e_apagada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Fato consumado. A aula aconteceu; encerrar não reescreve histórico."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Historico")
        matricula = criar_matricula(db, criar_paciente(db, "Veio"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        reserva = db.execute(
            select(Booking).where(Booking.enrollment_id == matricula.id).limit(1)
        ).scalar_one()
        booking_service.registrar_presenca(db, reserva.id)

        enrollment_service.encerrar(db, matricula.id)

        assert booking_service.buscar(db, reserva.id).status is StatusReserva.PRESENTE

    def test_falta_registrada_nao_e_apagada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Sumir com a falta apagaria o direito à reposição."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Falta Hist")
        matricula = criar_matricula(db, criar_paciente(db, "Faltou"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        reserva = db.execute(
            select(Booking).where(Booking.enrollment_id == matricula.id).limit(1)
        ).scalar_one()
        booking_service.registrar_falta(db, reserva.id, justificada=True)

        enrollment_service.encerrar(db, matricula.id)

        assert booking_service.buscar(db, reserva.id).status is StatusReserva.FALTA

    def test_suspender_libera_e_reativar_regenera(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Suspende")
        matricula = criar_matricula(db, criar_paciente(db, "Pausa"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        enrollment_service.suspender(db, matricula.id, motivo="Viagem")
        assert enrollment_service.buscar(db, matricula.id).status is StatusMatricula.SUSPENSA

        r = enrollment_service.reativar(db, matricula.id, criado_por_id=recepcao.id)

        assert enrollment_service.buscar(db, matricula.id).status is StatusMatricula.ATIVA
        assert r.reservas_criadas > 0

    def test_reativar_recusa_se_o_lugar_foi_vendido(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Enquanto suspensa, a vaga pode ter sido ocupada por outra matrícula."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Vendido", capacidade=1)
        matricula = criar_matricula(db, criar_paciente(db, "Suspendeu"), instrutor, servico)
        enrollment_service.suspender(db, matricula.id)
        criar_matricula(db, criar_paciente(db, "Assumiu"), instrutor, servico)

        with pytest.raises(HTTPException) as exc:
            enrollment_service.reativar(db, matricula.id, criado_por_id=recepcao.id)

        assert exc.value.status_code == 409


class TestBlackouts:
    def test_blackout_nao_gera_sessao(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Feriado")
        criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)
        # Bloqueia as próximas 8 semanas inteiras.
        enrollment_service.criar_blackout(
            db,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(weeks=9),
            motivo="Recesso",
        )

        r = enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)

        assert r.sessoes_criadas == 0
        assert r.dias_em_blackout > 0

    def test_blackout_criado_depois_avisa_e_nao_apaga(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Mesmo princípio da redução de capacidade: avisa, não decide sozinho."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Depois")
        criar_matricula(db, criar_paciente(db, "Aluno"), instrutor, servico)
        enrollment_service.gerar_grade(db, criado_por_id=recepcao.id)
        antes = db.execute(select(func.count()).select_from(Sessao)).scalar_one()

        _, conflito = enrollment_service.criar_blackout(
            db,
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(weeks=9),
            motivo="Reforma",
        )

        depois = db.execute(select(func.count()).select_from(Sessao)).scalar_one()
        assert depois == antes, "nenhuma sessão pode ser apagada em silêncio"
        assert len(conflito.sessoes) > 0, "o conflito precisa ser reportado"
        assert conflito.reservas_ativas > 0
