"""Reposições pendentes — o item de maior retorno do sistema.

Hoje isso vive na cabeça da Dra. Belanir. Tudo aqui é consulta sobre o que já
existe; nada é armazenado, então não há o que sair de sincronia.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.booking import Booking, OrigemReserva
from app.models.configuracao import Configuracao, JanelaReposicao
from app.models.user import User
from app.services import booking_service, reposicao_service
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_matricula,
    criar_paciente,
    criar_servico,
    criar_sessao,
    login,
    proxima_segunda,
)


def _faltar(
    db: Session, instrutor: User, recepcao: User, *, justificada: bool, hora: int = 8
) -> Booking:
    sessao = criar_sessao(db, instrutor, hora=hora)
    reserva = booking_service.criar(
        db,
        session_id=sessao.id,
        patient_id=criar_paciente(db, f"Faltante {hora}").id,
        criado_por_id=recepcao.id,
    )
    booking_service.registrar_falta(
        db, reserva.id, justificada=justificada, motivo="Atestado" if justificada else None
    )
    return reserva


class TestListagem:
    def test_falta_justificada_aparece(self, db: Session, instrutor: User, recepcao: User) -> None:
        criar_configuracao(db)
        reserva = _faltar(db, instrutor, recepcao, justificada=True)

        pendentes = reposicao_service.listar_pendentes(db)

        assert [p.booking_id for p in pendentes] == [reserva.id]

    def test_falta_nao_justificada_nao_aparece(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Configuração confirmada pela cliente (P5)."""
        criar_configuracao(db)
        _faltar(db, instrutor, recepcao, justificada=False)

        assert reposicao_service.listar_pendentes(db) == []

    def test_config_sem_exigir_justificativa_inclui_todas(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A regra é configuração, não código — trocar é editar um registro."""
        criar_configuracao(db)
        cfg = db.get(Configuracao, 1)
        assert cfg is not None
        cfg.reposicao_exige_justificativa = False
        db.flush()
        _faltar(db, instrutor, recepcao, justificada=False)

        assert len(reposicao_service.listar_pendentes(db)) == 1

    def test_falta_ja_reposta_sai_da_lista(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        falta = _faltar(db, instrutor, recepcao, justificada=True)
        destino = criar_sessao(db, instrutor, hora=9)

        booking_service.criar(
            db,
            session_id=destino.id,
            patient_id=falta.patient_id,
            criado_por_id=recepcao.id,
            origem=OrigemReserva.REPOSICAO,
            substitui_booking_id=falta.id,
        )

        assert reposicao_service.listar_pendentes(db) == []

    def test_reposicao_cancelada_devolve_o_direito(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Se a reposição foi cancelada, a falta volta a estar pendente."""
        criar_configuracao(db)
        falta = _faltar(db, instrutor, recepcao, justificada=True)
        destino = criar_sessao(db, instrutor, hora=9)
        reposicao = booking_service.criar(
            db,
            session_id=destino.id,
            patient_id=falta.patient_id,
            criado_por_id=recepcao.id,
            origem=OrigemReserva.REPOSICAO,
            substitui_booking_id=falta.id,
        )
        assert reposicao_service.listar_pendentes(db) == []

        booking_service.cancelar(db, reposicao.id, motivo="Não pôde vir")

        assert len(reposicao_service.listar_pendentes(db)) == 1

    def test_traz_o_que_a_recepcao_precisa_para_ligar(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor)
        paciente = criar_paciente(db, "Maria Silva")
        paciente.telefone = "11987654321"
        reserva = booking_service.criar(
            db, session_id=sessao.id, patient_id=paciente.id, criado_por_id=recepcao.id
        )
        booking_service.registrar_falta(db, reserva.id, justificada=True, motivo="Consulta médica")

        p = reposicao_service.listar_pendentes(db)[0]

        assert p.paciente_nome == "Maria Silva"
        assert p.paciente_telefone == "11987654321"
        assert p.motivo == "Consulta médica"
        assert p.faltou_em.date() == proxima_segunda()
        assert p.repor_ate is not None


class TestJanelaDeReposicao:
    """A janela é OPERACIONAL e independente do ciclo de cobrança.

    Os dois só se parecem por usarem a palavra "mês" — ver premissas.md (P2).
    """

    def test_padrao_e_fim_do_mes_do_calendario(self, db: Session) -> None:
        criar_configuracao(db)
        cfg = db.get(Configuracao, 1)
        assert cfg is not None
        assert cfg.janela_reposicao is JanelaReposicao.MES_CALENDARIO

        limite = reposicao_service.prazo_para_repor(db, date(2026, 3, 10), None)

        assert limite == date(2026, 3, 31)

    def test_fevereiro_respeita_o_ultimo_dia(self, db: Session) -> None:
        criar_configuracao(db)

        assert reposicao_service.prazo_para_repor(db, date(2026, 2, 5), None) == date(2026, 2, 28)

    def test_janela_independe_do_dia_de_vencimento(self, db: Session, instrutor: User) -> None:
        """O ponto da decisão: janela e ciclo de cobrança são separados.

        Um paciente que vence dia 15 tem a MESMA janela de quem vence dia 3,
        enquanto a configuração for mês do calendário.
        """
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Janela")
        matricula = criar_matricula(
            db,
            criar_paciente(db, "Vence Dia 15"),
            instrutor,
            servico,
            inicio=date(2026, 1, 15),
        )
        assert matricula.dia_vencimento == 15

        limite = reposicao_service.prazo_para_repor(db, date(2026, 3, 10), matricula)

        assert limite == date(2026, 3, 31), "mês do calendário, não o ciclo dele"

    def test_trocar_para_ciclo_do_paciente_sem_migration(
        self, db: Session, instrutor: User
    ) -> None:
        """Caso a cliente confirme o contrário, é editar um registro."""
        criar_configuracao(db)
        cfg = db.get(Configuracao, 1)
        assert cfg is not None
        cfg.janela_reposicao = JanelaReposicao.CICLO_DO_PACIENTE
        db.flush()

        servico = criar_servico(db, nome="Pilates Ciclo")
        matricula = criar_matricula(
            db,
            criar_paciente(db, "Ciclo 15"),
            instrutor,
            servico,
            inicio=date(2026, 1, 15),
        )

        limite = reposicao_service.prazo_para_repor(db, date(2026, 3, 10), matricula)

        assert limite == date(2026, 3, 14), "véspera do vencimento dele"

    def test_sem_prazo(self, db: Session) -> None:
        criar_configuracao(db)
        cfg = db.get(Configuracao, 1)
        assert cfg is not None
        cfg.janela_reposicao = JanelaReposicao.SEM_PRAZO
        db.flush()

        assert reposicao_service.prazo_para_repor(db, date(2026, 3, 10), None) is None


class TestApi:
    def test_recepcao_ve_as_pendentes_com_janela_de_busca(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        _faltar(db, instrutor, recepcao, justificada=True)
        t = login(client, recepcao.email)

        r = client.get("/api/v1/reposicoes-pendentes", headers=auth(t))

        assert r.status_code == 200
        item = r.json()[0]
        assert item["paciente_nome"]
        assert item["repor_ate"] is not None
        # A janela de busca é o que a tela usa para listar horários com vaga.
        assert item["procurar_de"] <= item["procurar_ate"]

    def test_instrutor_nao_acessa(self, client: TestClient, db: Session, instrutor: User) -> None:
        criar_configuracao(db)
        t = login(client, instrutor.email)

        assert client.get("/api/v1/reposicoes-pendentes", headers=auth(t)).status_code == 403

    def test_fluxo_completo_faltar_e_repor(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Da falta até a reposição, como a recepção faria."""
        criar_configuracao(db)
        falta = _faltar(db, instrutor, recepcao, justificada=True)
        destino = criar_sessao(db, instrutor, hora=10)
        db.commit()
        t = login(client, recepcao.email)

        pendentes = client.get("/api/v1/reposicoes-pendentes", headers=auth(t)).json()
        assert len(pendentes) == 1
        item = pendentes[0]

        vagas = client.get(
            "/api/v1/agenda/vagas",
            params={
                "de": item["procurar_de"],
                "ate": item["procurar_ate"],
                "excluir_patient_id": item["patient_id"],
            },
            headers=auth(t),
        ).json()
        assert any(v["id"] == destino.id for v in vagas)

        r = client.post(
            "/api/v1/bookings",
            json={
                "session_id": destino.id,
                "patient_id": item["patient_id"],
                "origem": "reposicao",
            },
            headers=auth(t),
        )
        assert r.status_code == 201

        # Vincula a reposição à falta e confirma que ela sai da lista.
        nova = db.get(Booking, r.json()["id"])
        assert nova is not None
        nova.substitui_booking_id = falta.id
        db.flush()

        assert reposicao_service.listar_pendentes(db) == []


class TestVinculoViaApi:
    def test_repor_pela_api_liga_a_falta_e_some_da_lista(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Sem `substitui_booking_id`, a falta ficaria pendente para sempre."""
        criar_configuracao(db)
        falta = _faltar(db, instrutor, recepcao, justificada=True)
        destino = criar_sessao(db, instrutor, hora=11)
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/bookings",
            json={
                "session_id": destino.id,
                "patient_id": falta.patient_id,
                "origem": "reposicao",
                "substitui_booking_id": falta.id,
            },
            headers=auth(t),
        )

        assert r.status_code == 201
        assert r.json()["substitui_booking_id"] == falta.id
        assert reposicao_service.listar_pendentes(db) == []

    def test_nao_repoe_a_mesma_falta_duas_vezes(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """Repor duas vezes seria overbooking por outra porta."""
        criar_configuracao(db)
        falta = _faltar(db, instrutor, recepcao, justificada=True)
        d1 = criar_sessao(db, instrutor, hora=11)
        d2 = criar_sessao(db, instrutor, hora=15)
        t = login(client, recepcao.email)
        corpo = {
            "patient_id": falta.patient_id,
            "origem": "reposicao",
            "substitui_booking_id": falta.id,
        }

        primeira = client.post(
            "/api/v1/bookings", json={**corpo, "session_id": d1.id}, headers=auth(t)
        )
        segunda = client.post(
            "/api/v1/bookings", json={**corpo, "session_id": d2.id}, headers=auth(t)
        )

        assert primeira.status_code == 201
        assert segunda.status_code == 409
        # A mensagem tem de dizer a causa REAL. "Turma completa" mandaria a
        # recepção procurar outro horário quando o horário não é o problema.
        assert "já foi reposta" in segunda.json()["detail"]
