"""Consistência de erro e ausência de dado pessoal nos logs."""

import json
import logging

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.logs import CAMPOS_PESSOAIS, FormatadorJson, sanitizar
from app.models.user import User
from tests.conftest import auth, criar_configuracao, login


class TestRespostasDeErro:
    def test_validacao_diz_qual_campo_e_por_que(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """O formato padrão do FastAPI é uma lista aninhada ilegível.

        A tela mostra `detail` direto para a recepcionista.
        """
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json={"nome_completo": "Teste Erro", "cpf": "111.111.111-11"},
            headers=auth(t),
        )

        assert r.status_code == 422
        detalhe = r.json()["detail"]
        assert isinstance(detalhe, str), "detail precisa ser texto legível"
        assert "cpf" in detalhe and "CPF inválido" in detalhe
        assert r.json()["campos"][0]["campo"] == "cpf"

    def test_resposta_de_erro_e_serializavel(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """O `ctx` do Pydantic carrega a exceção original.

        Incluí-la fazia o próprio handler de erro estourar — 500 em cima de
        um 422, que é o pior desfecho possível.
        """
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json={"nome_completo": "x"}, headers=auth(t))

        assert r.status_code == 422
        json.dumps(r.json())  # não pode levantar

    def test_nenhum_500_com_traceback_na_resposta(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """Nada de detalhe interno na tela, em nenhum caminho."""
        criar_configuracao(db)
        t = login(client, recepcao.email)

        respostas = [
            client.get("/api/v1/patients/999999", headers=auth(t)),
            client.get("/api/v1/charges/999999", headers=auth(t)),
            client.post(
                "/api/v1/bookings", json={"session_id": 9, "patient_id": 9}, headers=auth(t)
            ),
            client.get(
                "/api/v1/agenda/semana", params={"referencia": "não-é-data"}, headers=auth(t)
            ),
        ]

        for r in respostas:
            assert r.status_code < 500, f"{r.request.url}: {r.status_code}"
            corpo = r.text.lower()
            for vazamento in ("traceback", "sqlalchemy", "psycopg", 'file "/'):
                assert vazamento not in corpo, f"vazou '{vazamento}' em {r.request.url}"

    def test_erro_previsivel_diz_o_que_fazer(
        self, client: TestClient, db: Session, instrutor: User, recepcao: User
    ) -> None:
        """No espírito de 'Esta falta já foi reposta'.

        Mensagem que só diz o que aconteceu manda a pessoa adivinhar o
        próximo passo.
        """
        from tests.conftest import criar_paciente, criar_sessao

        criar_configuracao(db)
        sessao = criar_sessao(db, instrutor, capacidade=1)
        db.commit()
        t = login(client, recepcao.email)
        a = criar_paciente(db, "Primeiro Erro")
        b = criar_paciente(db, "Segundo Erro")
        db.commit()

        client.post(
            "/api/v1/bookings",
            json={"session_id": sessao.id, "patient_id": a.id},
            headers=auth(t),
        )
        r = client.post(
            "/api/v1/bookings",
            json={"session_id": sessao.id, "patient_id": b.id},
            headers=auth(t),
        )

        assert r.status_code == 409
        assert "turma completa" in r.json()["detail"]

    def test_404_e_404_e_nao_500(self, client: TestClient, db: Session, recepcao: User) -> None:
        t = login(client, recepcao.email)

        assert client.get("/api/v1/patients/999999", headers=auth(t)).status_code == 404
        assert client.get("/api/v1/charges/999999", headers=auth(t)).status_code == 404


class TestPaginacaoConsistente:
    def test_listagens_paginadas_tem_o_mesmo_formato(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """`itens`, `total`, `pagina`, `tamanho` em toda listagem paginada."""
        criar_configuracao(db)
        t = login(client, recepcao.email)

        for rota in ("/api/v1/patients", "/api/v1/charges"):
            corpo = client.get(rota, headers=auth(t)).json()
            assert set(corpo) >= {"itens", "total", "pagina", "tamanho"}, rota

    def test_limites_de_pagina_sao_validados(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)

        assert (
            client.get("/api/v1/patients", params={"pagina": 0}, headers=auth(t)).status_code == 422
        )
        assert (
            client.get("/api/v1/patients", params={"tamanho": 5000}, headers=auth(t)).status_code
            == 422
        )

    def test_pagina_alem_do_fim_devolve_lista_vazia_e_nao_erro(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"pagina": 999}, headers=auth(t))

        assert r.status_code == 200
        assert r.json()["itens"] == []


class TestLogsSemDadoPessoal:
    def test_campos_pessoais_sao_removidos(self) -> None:
        limpo = sanitizar(
            {
                "paciente_id": 42,
                "nome_completo": "Maria Silva",
                "cpf": "52998224725",
                "telefone": "11987654321",
                "rota": "/api/v1/patients",
            }
        )

        assert limpo["paciente_id"] == 42, "id pode: quem tem o banco resolve"
        assert limpo["rota"] == "/api/v1/patients"
        assert limpo["nome_completo"] == "[removido]"
        assert limpo["cpf"] == "[removido]"
        assert limpo["telefone"] == "[removido]"

    def test_a_lista_cobre_os_campos_sensiveis_do_modelo(self) -> None:
        """Guarda: campo pessoal novo no model precisa entrar aqui."""
        for campo in ("nome_completo", "cpf", "telefone", "email", "senha"):
            assert campo in CAMPOS_PESSOAIS

    def test_formatador_gera_json_valido(self) -> None:
        registro = logging.LogRecord("teste", logging.INFO, "arq.py", 1, "mensagem", None, None)
        registro.contexto = {"rota": "/x", "cpf": "52998224725"}  # type: ignore[attr-defined]

        saida = json.loads(FormatadorJson().format(registro))

        assert saida["msg"] == "mensagem"
        assert saida["cpf"] == "[removido]"

    def test_requisicao_devolve_id_de_correlacao(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """Sem id, ninguém liga o erro na tela ao evento no log."""
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", headers=auth(t))

        assert r.headers.get("X-Request-Id")
