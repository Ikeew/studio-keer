"""A capacidade é inviolável. Estes testes são a prova.

A dor número um da cliente é overbooking; se algum destes testes ficar
vermelho, o sistema deixou de resolver o problema para o qual foi feito.
"""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.booking import Booking, OrigemReserva, StatusReserva
from app.models.user import Papel, User
from app.services import booking_service
from tests.conftest import criar_paciente, criar_servico, criar_sessao, criar_usuario


def _reservar(db: Session, sessao_id: int, paciente_id: int, quem: User, **kw: object) -> Booking:
    return booking_service.criar(
        db,
        session_id=sessao_id,
        patient_id=paciente_id,
        criado_por_id=quem.id,
        **kw,  # type: ignore[arg-type]
    )


class TestLimiteDeCapacidade:
    def test_preenche_ate_a_capacidade(self, db: Session, instrutor: User, recepcao: User) -> None:
        sessao = criar_sessao(db, instrutor, capacidade=4)

        for i in range(4):
            _reservar(db, sessao.id, criar_paciente(db, f"P{i}").id, recepcao)

        assert booking_service.vagas_livres(db, sessao) == 0

    def test_a_quinta_reserva_e_recusada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        sessao = criar_sessao(db, instrutor, capacidade=4)
        for i in range(4):
            _reservar(db, sessao.id, criar_paciente(db, f"P{i}").id, recepcao)

        with pytest.raises(HTTPException) as exc:
            _reservar(db, sessao.id, criar_paciente(db, "Quinto").id, recepcao)

        assert exc.value.status_code == 409
        assert "completa" in exc.value.detail

    def test_reposicao_nao_tem_excecao(self, db: Session, instrutor: User, recepcao: User) -> None:
        """A regra central do projeto.

        A hipótese é que reposição encaixada de cabeça causa o overbooking.
        Aqui ela passa pelo mesmo limite de qualquer reserva — sem "encaixe".
        """
        sessao = criar_sessao(db, instrutor, capacidade=4)
        for i in range(4):
            _reservar(db, sessao.id, criar_paciente(db, f"P{i}").id, recepcao)

        with pytest.raises(HTTPException) as exc:
            _reservar(
                db,
                sessao.id,
                criar_paciente(db, "Repondo").id,
                recepcao,
                origem=OrigemReserva.REPOSICAO,
            )

        assert exc.value.status_code == 409

    def test_avaliacao_individual_aceita_uma_so(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        sessao = criar_sessao(db, instrutor, capacidade=1)
        _reservar(db, sessao.id, criar_paciente(db, "Unico").id, recepcao)

        with pytest.raises(HTTPException) as exc:
            _reservar(db, sessao.id, criar_paciente(db, "Segundo").id, recepcao)

        assert exc.value.status_code == 409

    def test_mesmo_paciente_nao_ocupa_duas_vagas(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        sessao = criar_sessao(db, instrutor, capacidade=4)
        paciente = criar_paciente(db)
        _reservar(db, sessao.id, paciente.id, recepcao)

        with pytest.raises(HTTPException) as exc:
            _reservar(db, sessao.id, paciente.id, recepcao)

        assert exc.value.status_code == 409


class TestTravaNoBanco:
    """A capacidade não depende só da aplicação estar correta."""

    def test_banco_recusa_posicao_duplicada(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Índice único parcial: duas reservas não dividem a mesma posição.

        Escrito direto no model, sem passar pelo serviço, justamente para
        provar que a garantia é do BANCO e não da camada de regra.
        """
        sessao = criar_sessao(db, instrutor, capacidade=4)
        db.add(
            Booking(
                session_id=sessao.id,
                patient_id=criar_paciente(db, "A").id,
                posicao=1,
                capacidade_sessao=4,
                origem=OrigemReserva.AVULSA,
                status=StatusReserva.AGENDADA,
                criado_por_id=recepcao.id,
            )
        )
        db.flush()

        db.add(
            Booking(
                session_id=sessao.id,
                patient_id=criar_paciente(db, "B").id,
                posicao=1,  # mesma posição
                capacidade_sessao=4,
                origem=OrigemReserva.AVULSA,
                status=StatusReserva.AGENDADA,
                criado_por_id=recepcao.id,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()

    def test_banco_recusa_posicao_acima_da_capacidade(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """CHECK (posicao <= capacidade_sessao).

        Fecha o furo que o índice único sozinho deixaria: um bug na aplicação
        que calculasse a posição 5 numa turma de 4 seria aceito pelo índice,
        mas é recusado por este CHECK.
        """
        sessao = criar_sessao(db, instrutor, capacidade=4)
        db.add(
            Booking(
                session_id=sessao.id,
                patient_id=criar_paciente(db, "Furando").id,
                posicao=5,
                capacidade_sessao=4,
                origem=OrigemReserva.AVULSA,
                status=StatusReserva.AGENDADA,
                criado_por_id=recepcao.id,
            )
        )

        with pytest.raises(IntegrityError):
            db.flush()


class TestConcorrencia:
    def test_duas_recepcionistas_disputando_a_ultima_vaga(self, engine: sa.Engine) -> None:
        """Duas transações REAIS competindo pela última vaga.

        Uma tem que vencer e a outra falhar com 409 — nunca 500, e nunca as
        duas passarem. É o cenário que a planilha da cliente não sabe impedir.

        Não usa as fixtures `db`/`recepcao`/`instrutor`: elas vivem numa
        transação não commitada, invisível para outras conexões. Aqui os dados
        são criados e commitados numa conexão própria, justamente para
        exercitar a serialização do banco de verdade. Por isso a limpeza no
        fim é explícita.
        """
        criar_sessao_db = sessionmaker(bind=engine, expire_on_commit=False)
        marca = uuid4().hex[:8]

        setup = criar_sessao_db()
        try:
            operador = criar_usuario(setup, Papel.RECEPCAO, email=f"r-{marca}@example.com")
            professor = criar_usuario(setup, Papel.INSTRUTOR, email=f"i-{marca}@example.com")
            servico = criar_servico(setup, nome=f"Disputa {marca}", capacidade=1)
            sessao = criar_sessao(setup, professor, servico=servico, capacidade=1, hora=9)
            p1 = criar_paciente(setup, f"Disputa A {marca}")
            p2 = criar_paciente(setup, f"Disputa B {marca}")
            setup.commit()
            ids = (sessao.id, p1.id, p2.id, operador.id, servico.id, professor.id, p1.id, p2.id)
        finally:
            setup.close()

        sessao_id, p1_id, p2_id, criador_id, servico_id, prof_id, _, _ = ids
        db_a, db_b = criar_sessao_db(), criar_sessao_db()
        resultados: list[str] = []
        try:
            booking_service.criar(
                db_a, session_id=sessao_id, patient_id=p1_id, criado_por_id=criador_id
            )
            db_a.commit()
            resultados.append("A ok")

            try:
                booking_service.criar(
                    db_b, session_id=sessao_id, patient_id=p2_id, criado_por_id=criador_id
                )
                db_b.commit()
                resultados.append("B ok")
            except HTTPException as exc:
                resultados.append(f"B recusada {exc.status_code}")
        finally:
            db_a.close()
            db_b.close()
            limpeza = criar_sessao_db()
            try:
                limpeza.execute(sa.delete(Booking).where(Booking.session_id == sessao_id))
                limpeza.execute(sa.text("DELETE FROM sessions WHERE id = :i"), {"i": sessao_id})
                limpeza.execute(
                    sa.text("DELETE FROM patients WHERE id in (:a, :b)"),
                    {"a": p1_id, "b": p2_id},
                )
                limpeza.execute(sa.text("DELETE FROM services WHERE id = :i"), {"i": servico_id})
                limpeza.execute(
                    sa.text("DELETE FROM users WHERE id in (:a, :b)"),
                    {"a": criador_id, "b": prof_id},
                )
                limpeza.commit()
            finally:
                limpeza.close()

        assert resultados[0] == "A ok"
        assert resultados[1] == "B recusada 409", (
            f"a segunda reserva deveria ter sido recusada, veio: {resultados[1]}"
        )


class TestCancelarLiberaVaga:
    """O valor operacional do aviso antecipado (premissas.md, P4)."""

    def test_cancelar_devolve_a_vaga(self, db: Session, instrutor: User, recepcao: User) -> None:
        sessao = criar_sessao(db, instrutor, capacidade=1)
        reserva = _reservar(db, sessao.id, criar_paciente(db, "Saiu").id, recepcao)
        assert booking_service.vagas_livres(db, sessao) == 0

        booking_service.cancelar(db, reserva.id, motivo="Avisou que não vem")

        assert booking_service.vagas_livres(db, sessao) == 1

    def test_vaga_liberada_recebe_reposicao(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """É assim que o cancelamento antecipado gera valor no studio dela.

        Não punindo quem avisa, mas devolvendo o horário a quem precisa repor.
        """
        sessao = criar_sessao(db, instrutor, capacidade=1)
        original = _reservar(db, sessao.id, criar_paciente(db, "Avisou").id, recepcao)
        booking_service.cancelar(db, original.id, motivo="Avisou com antecedência")

        reposicao = _reservar(
            db,
            sessao.id,
            criar_paciente(db, "Repondo").id,
            recepcao,
            origem=OrigemReserva.REPOSICAO,
        )

        assert reposicao.id is not None
        assert reposicao.posicao == 1, "reaproveita a posição que vagou"

    def test_falta_continua_ocupando_a_vaga(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Falta NÃO é cancelamento.

        A aula aconteceu com aquele lugar reservado. O que a falta gera é
        direito a repor em OUTRO horário — que ocupará outra vaga.
        """
        sessao = criar_sessao(db, instrutor, capacidade=1)
        reserva = _reservar(db, sessao.id, criar_paciente(db, "Faltou").id, recepcao)

        booking_service.registrar_falta(db, reserva.id, justificada=True)

        assert booking_service.vagas_livres(db, sessao) == 0
