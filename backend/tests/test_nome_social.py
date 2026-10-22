"""Nome social: como a pessoa gosta de ser chamada.

Telas do dia a dia (agenda, presença, reposição) mostram o nome social
quando houver. Financeiro e documento fiscal continuam no nome civil.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.charge import Charge, TipoCobranca
from app.models.user import User
from app.services import booking_service, dashboard_service, reposicao_service
from tests.conftest import (
    auth,
    criar_configuracao,
    criar_paciente,
    criar_sessao,
    login,
    proxima_segunda,
)

CIVIL = "Roberto Almeida"
SOCIAL = "Bia Almeida"


class TestCadastro:
    def test_cria_com_nome_social(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json={"nome_completo": CIVIL, "nome_social": f"  {SOCIAL}  "},
            headers=auth(t),
        )

        assert r.status_code == 201
        assert r.json()["nome_social"] == SOCIAL
        assert r.json()["nome_exibicao"] == SOCIAL

    def test_opcional_e_em_branco_e_nenhum(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json={"nome_completo": CIVIL, "nome_social": "   "},
            headers=auth(t),
        )

        assert r.json()["nome_social"] is None
        assert r.json()["nome_exibicao"] == CIVIL

    def test_apagar_pelo_update(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        criado = client.post(
            "/api/v1/patients",
            json={"nome_completo": CIVIL, "nome_social": SOCIAL},
            headers=auth(t),
        ).json()

        r = client.patch(
            f"/api/v1/patients/{criado['id']}", json={"nome_social": None}, headers=auth(t)
        )

        assert r.status_code == 200
        assert r.json()["nome_social"] is None

    def test_busca_encontra_pelo_nome_social(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        p = criar_paciente(db, CIVIL)
        p.nome_social = SOCIAL
        db.flush()
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"busca": "Bia"}, headers=auth(t))

        assert [i["id"] for i in r.json()["itens"]] == [p.id]


class TestOndeAparece:
    def _paciente_na_turma(self, db: Session, instrutor: User, recepcao: User) -> int:
        criar_configuracao(db)
        paciente = criar_paciente(db, CIVIL)
        paciente.nome_social = SOCIAL
        sessao = criar_sessao(db, instrutor)
        reserva = booking_service.criar(
            db, session_id=sessao.id, patient_id=paciente.id, criado_por_id=recepcao.id
        )
        return reserva.id

    def test_agenda_usa_o_nome_social(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        self._paciente_na_turma(db, instrutor, recepcao)
        t = login(client, recepcao.email)

        grade = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": proxima_segunda().isoformat()},
            headers=auth(t),
        ).json()

        nomes = [r["paciente_nome"] for s in grade["sessoes"] for r in s["reservas"]]
        assert nomes == [SOCIAL]

    def test_reposicao_usa_o_nome_social(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        reserva_id = self._paciente_na_turma(db, instrutor, recepcao)
        booking_service.registrar_falta(db, reserva_id, justificada=True)

        assert [p.paciente_nome for p in reposicao_service.listar_pendentes(db)] == [SOCIAL]

    def test_agenda_do_instrutor_usa_o_nome_social(
        self, db: Session, instrutor: User, recepcao: User
    ) -> None:
        self._paciente_na_turma(db, instrutor, recepcao)

        proximos = dashboard_service._proximos_de(
            db, proxima_segunda(), professional_id=instrutor.id, limite=10
        )

        assert [p.paciente_nome for p in proximos] == [SOCIAL]

    def test_financeiro_usa_o_nome_civil(
        self, client: TestClient, db: Session, admin: User
    ) -> None:
        """Nota fiscal e contrato saem no nome civil."""
        paciente = criar_paciente(db, CIVIL)
        paciente.nome_social = SOCIAL
        db.add(
            Charge(
                patient_id=paciente.id,
                tipo=TipoCobranca.AVULSA,
                descricao="Avaliação",
                valor_centavos=10_000,
                vencimento=proxima_segunda(),
            )
        )
        db.flush()
        t = login(client, admin.email)

        itens = client.get("/api/v1/charges", headers=auth(t)).json()["itens"]

        assert [c["paciente_nome"] for c in itens] == [CIVIL]
