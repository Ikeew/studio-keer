"""Fluxos ponta a ponta, pela API, como cada papel os executaria.

Os testes anteriores cobrem regras isoladas. Estes cobrem a JORNADA: se um
passo quebrar o contrato do seguinte, aparece aqui e não na demonstração.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from tests.conftest import auth, criar_configuracao, criar_servico, login, proxima_segunda


def _prox_dia_util(offset_semanas: int = 0) -> date:
    return proxima_segunda() + timedelta(weeks=offset_semanas)


class TestJornadaDaRecepcao:
    """Cadastra paciente → matricula → gera grade → falta → repõe → recebe."""

    def test_do_cadastro_ao_pagamento(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates E2E", capacidade=4)
        db.commit()
        t = login(client, recepcao.email)

        # 1. Cadastra o paciente.
        paciente = client.post(
            "/api/v1/patients",
            json={
                "nome_completo": "Joana E2E",
                "cpf": "529.982.247-25",
                "telefone": "(11) 98765-4321",
                "consentimento_lgpd": True,
            },
            headers=auth(t),
        )
        assert paciente.status_code == 201, paciente.text
        pid = paciente.json()["id"]
        assert paciente.json()["consentimento_em"] is not None

        # 2. Matricula num horário fixo.
        matricula = client.post(
            "/api/v1/enrollments",
            json={
                "patient_id": pid,
                "service_id": servico.id,
                "professional_id": instrutor.id,
                "vigencia_inicio": str(date.today() - timedelta(days=40)),
                "valor_mensal_centavos": 20_000,
                "horarios": [{"dia_semana": 1, "hora_inicio": "08:00:00"}],
            },
            headers=auth(t),
        )
        assert matricula.status_code == 201, matricula.text
        assert matricula.json()["frequencia_semanal"] == 1

        # 3. Gera a grade recorrente.
        grade = client.post("/api/v1/enrollments/gerar-grade", headers=auth(t))
        assert grade.status_code == 200
        assert grade.json()["reservas_criadas"] > 0

        # A agenda passa a mostrar o paciente.
        semana = client.get(
            "/api/v1/agenda/semana",
            params={"referencia": str(proxima_segunda())},
            headers=auth(t),
        ).json()
        reservas = [r for s in semana["sessoes"] for r in s["reservas"]]
        assert any(r["paciente_nome"] == "Joana E2E" for r in reservas)

        # 4. Marca falta justificada.
        alvo = next(r for r in reservas if r["paciente_nome"] == "Joana E2E")
        falta = client.post(
            f"/api/v1/bookings/{alvo['id']}/falta",
            json={"justificada": True, "motivo": "Atestado médico"},
            headers=auth(t),
        )
        assert falta.status_code == 200
        assert falta.json()["justificada"] is True

        # 5. A falta aparece como reposição pendente.
        pendentes = client.get("/api/v1/reposicoes-pendentes", headers=auth(t)).json()
        minha = next(p for p in pendentes if p["patient_id"] == pid)
        assert minha["repor_ate"] is not None

        # 6. Abre uma turma em outro horário, para haver onde repor.
        #    É o que a recepção faz quando precisa acomodar alguém.
        nova_turma = client.post(
            "/api/v1/sessions",
            json={
                "service_id": servico.id,
                "professional_id": instrutor.id,
                "inicia_em": f"{proxima_segunda() + timedelta(days=2)}T10:00:00",
            },
            headers=auth(t),
        )
        assert nova_turma.status_code == 201, nova_turma.text

        # 7. Procura vaga e agenda a reposição.
        vagas = client.get(
            "/api/v1/agenda/vagas",
            params={
                "de": minha["procurar_de"],
                "ate": minha["procurar_ate"],
                "excluir_patient_id": pid,
            },
            headers=auth(t),
        ).json()
        assert vagas, "sem vaga não há como demonstrar a reposição"

        reposicao = client.post(
            "/api/v1/bookings",
            json={
                "session_id": vagas[0]["id"],
                "patient_id": pid,
                "origem": "reposicao",
                "substitui_booking_id": minha["booking_id"],
            },
            headers=auth(t),
        )
        assert reposicao.status_code == 201
        assert reposicao.json()["substitui_booking_id"] == minha["booking_id"]

        # 8. A falta sai da lista de pendentes.
        depois = client.get("/api/v1/reposicoes-pendentes", headers=auth(t)).json()
        assert all(p["patient_id"] != pid for p in depois)

        # 9. Emite e recebe a mensalidade.
        emissao = client.post("/api/v1/charges/gerar-mensalidades", headers=auth(t))
        assert emissao.status_code == 200

        cobrancas = client.get(
            "/api/v1/charges", params={"busca": "Joana E2E"}, headers=auth(t)
        ).json()
        assert cobrancas["total"] > 0
        cobranca = cobrancas["itens"][0]

        pago = client.post(
            f"/api/v1/charges/{cobranca['id']}/pagar",
            json={"forma_pagamento": "pix"},
            headers=auth(t),
        )
        assert pago.status_code == 200 and pago.json()["status"] == "pago"

        # 10. Errou a baixa? Desfaz sem chamar a proprietária.
        desfeito = client.post(f"/api/v1/charges/{cobranca['id']}/desfazer", headers=auth(t))
        assert desfeito.status_code == 200 and desfeito.json()["status"] == "pendente"

    def test_a_quinta_matricula_no_mesmo_horario_e_recusada(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """A cena central da apresentação, pela API."""
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Cheio E2E", capacidade=4)
        db.commit()
        t = login(client, recepcao.email)

        respostas = []
        for i in range(5):
            pid = client.post(
                "/api/v1/patients", json={"nome_completo": f"Aluno E2E {i}"}, headers=auth(t)
            ).json()["id"]
            respostas.append(
                client.post(
                    "/api/v1/enrollments",
                    json={
                        "patient_id": pid,
                        "service_id": servico.id,
                        "professional_id": instrutor.id,
                        "vigencia_inicio": str(date.today()),
                        "valor_mensal_centavos": 20_000,
                        "horarios": [{"dia_semana": 1, "hora_inicio": "08:00:00"}],
                    },
                    headers=auth(t),
                )
            )

        assert [r.status_code for r in respostas] == [201, 201, 201, 201, 409]
        detalhe = respostas[4].json()["detail"]
        assert "é o horário" in detalhe, "a mensagem tem de dizer que o problema é o horário"
        assert "alunos fixos" in detalhe


class TestJornadaDoAdmin:
    def test_cancela_cobranca_e_cria_blackout(
        self, client: TestClient, db: Session, instrutor: User, admin: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Admin E2E", capacidade=4)
        db.commit()
        t = login(client, admin.email)

        pid = client.post(
            "/api/v1/patients", json={"nome_completo": "Paciente Admin E2E"}, headers=auth(t)
        ).json()["id"]
        client.post(
            "/api/v1/enrollments",
            json={
                "patient_id": pid,
                "service_id": servico.id,
                "professional_id": instrutor.id,
                "vigencia_inicio": str(date.today() - timedelta(days=40)),
                "valor_mensal_centavos": 20_000,
                "horarios": [{"dia_semana": 1, "hora_inicio": "09:00:00"}],
            },
            headers=auth(t),
        )
        client.post("/api/v1/enrollments/gerar-grade", headers=auth(t))
        client.post("/api/v1/charges/gerar-mensalidades", headers=auth(t))

        cobranca = client.get(
            "/api/v1/charges", params={"busca": "Paciente Admin E2E"}, headers=auth(t)
        ).json()["itens"][0]
        cancelada = client.request(
            "DELETE",
            f"/api/v1/charges/{cobranca['id']}",
            json={"motivo": "Cortesia"},
            headers=auth(t),
        )
        assert cancelada.status_code == 200 and cancelada.json()["status"] == "cancelado"

        # Blackout AVISA e não apaga.
        inicio = _prox_dia_util(2)
        blackout = client.post(
            "/api/v1/blackouts",
            json={
                "data_inicio": str(inicio),
                "data_fim": str(inicio + timedelta(days=6)),
                "motivo": "Recesso E2E",
            },
            headers=auth(t),
        )
        assert blackout.status_code == 201
        corpo = blackout.json()
        assert corpo["sessoes_em_conflito"], "o conflito precisa ser reportado"

        semana = client.get(
            "/api/v1/agenda/semana", params={"referencia": str(inicio)}, headers=auth(t)
        ).json()
        assert semana["sessoes"], "nenhuma sessão pode ser apagada em silêncio"

    def test_admin_ve_o_dashboard_completo(
        self, client: TestClient, db: Session, admin: User
    ) -> None:
        criar_configuracao(db)
        t = login(client, admin.email)

        for rota in ("/api/v1/dashboard", "/api/v1/dashboard/servicos", "/api/v1/charges"):
            assert client.get(rota, headers=auth(t)).status_code == 200, rota


class TestJornadaDoInstrutor:
    def test_ve_a_agenda_do_dia_e_e_barrado_no_resto(
        self, client: TestClient, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        db.commit()
        t = login(client, instrutor.email)

        # O que ele PODE.
        assert client.get("/api/v1/dashboard/minha-agenda", headers=auth(t)).status_code == 200
        assert client.get("/api/v1/agenda/semana", headers=auth(t)).status_code == 200
        assert client.get("/api/v1/agenda/saude-da-grade", headers=auth(t)).status_code == 200

        # O que ele NÃO pode — leitura de dado que não é dele.
        for rota in (
            "/api/v1/patients",
            "/api/v1/services",
            "/api/v1/charges",
            "/api/v1/charges/totais",
            "/api/v1/packages",
            "/api/v1/enrollments",
            "/api/v1/reposicoes-pendentes",
            "/api/v1/dashboard",
            "/api/v1/dashboard/servicos",
            "/api/v1/users",
            "/api/v1/instrutores",
        ):
            assert client.get(rota, headers=auth(t)).status_code == 403, rota

    def test_instrutor_nao_escreve_nada(
        self, client: TestClient, db: Session, instrutor: User
    ) -> None:
        criar_configuracao(db)
        servico = criar_servico(db, nome="Pilates Instrutor E2E")
        db.commit()
        t = login(client, instrutor.email)

        assert (
            client.post(
                "/api/v1/patients", json={"nome_completo": "Não Deve Existir"}, headers=auth(t)
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/sessions",
                json={
                    "service_id": servico.id,
                    "professional_id": instrutor.id,
                    "inicia_em": f"{proxima_segunda()}T08:00:00",
                },
                headers=auth(t),
            ).status_code
            == 403
        )
        assert client.post("/api/v1/enrollments/gerar-grade", headers=auth(t)).status_code == 403
        assert client.post("/api/v1/charges/gerar-mensalidades", headers=auth(t)).status_code == 403
