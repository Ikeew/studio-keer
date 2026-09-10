from fastapi.testclient import TestClient

from app.models.user import User
from tests.conftest import auth, login


def mensalidade(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "nome": "Pilates",
        "duracao_min": 60,
        "preco_centavos": 10_000,
        "capacidade_padrao": 4,
        "cor": "#06B6D4",
        "modelo_cobranca": "mensalidade",
    }
    base.update(extra)
    return base


def pacote(**extra: object) -> dict[str, object]:
    base = mensalidade(nome="Fisioterapia", modelo_cobranca="pacote")
    base.update(extra)
    return base


class TestCriar:
    def test_cria_servico_de_mensalidade(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/services", json=mensalidade(), headers=auth(t))

        assert r.status_code == 201
        assert r.json()["modelo_cobranca"] == "mensalidade"

    def test_capacidade_1_para_avaliacao(self, client: TestClient, recepcao: User) -> None:
        """Avaliação é individual — confirmado pela cliente (P1)."""
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/services",
            json=mensalidade(nome="Avaliação", capacidade_padrao=1),
            headers=auth(t),
        )

        assert r.json()["capacidade_padrao"] == 1

    def test_recusa_capacidade_zero(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/services", json=mensalidade(capacidade_padrao=0), headers=auth(t))

        assert r.status_code == 422

    def test_recusa_cor_fora_do_formato_hex(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/services", json=mensalidade(cor="azul"), headers=auth(t))

        assert r.status_code == 422

    def test_nome_duplicado_da_409(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        client.post("/api/v1/services", json=mensalidade(), headers=auth(t))

        r = client.post("/api/v1/services", json=mensalidade(), headers=auth(t))

        assert r.status_code == 409


class TestSugestaoDePacote:
    """Os campos de sugestão só fazem sentido em serviço vendido como pacote.

    Validado no backend, não só escondido na tela: a API é chamável direto.
    """

    def test_aceita_sugestao_em_servico_de_pacote(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/services",
            json=pacote(
                sugestao_pacote_sessoes=10,
                sugestao_pacote_validade_dias=90,
                sugestao_pacote_valor_centavos=100_000,
            ),
            headers=auth(t),
        )

        assert r.status_code == 201
        assert r.json()["sugestao_pacote_sessoes"] == 10

    def test_recusa_sugestao_em_servico_de_mensalidade(
        self, client: TestClient, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/services",
            json=mensalidade(sugestao_pacote_sessoes=10),
            headers=auth(t),
        )

        assert r.status_code == 422
        assert "sugestao_pacote_sessoes" in r.text

    def test_pacote_sem_sugestao_e_valido(self, client: TestClient, recepcao: User) -> None:
        """Sugestão nunca é obrigatória — o valor real é negociado na venda."""
        t = login(client, recepcao.email)

        r = client.post("/api/v1/services", json=pacote(), headers=auth(t))

        assert r.status_code == 201
        assert r.json()["sugestao_pacote_sessoes"] is None

    def test_trocar_para_mensalidade_exige_limpar_a_sugestao(
        self, client: TestClient, recepcao: User
    ) -> None:
        """Sem isso, sugestões antigas ficariam órfãs num serviço de mensalidade."""
        t = login(client, recepcao.email)
        sid = client.post(
            "/api/v1/services",
            json=pacote(sugestao_pacote_sessoes=10),
            headers=auth(t),
        ).json()["id"]

        r = client.put(
            f"/api/v1/services/{sid}",
            json=pacote(modelo_cobranca="mensalidade", sugestao_pacote_sessoes=10),
            headers=auth(t),
        )

        assert r.status_code == 422


class TestPermissoes:
    def test_instrutor_nao_lista_servicos(self, client: TestClient, instrutor: User) -> None:
        t = login(client, instrutor.email)

        assert client.get("/api/v1/services", headers=auth(t)).status_code == 403

    def test_recepcao_cria_mas_nao_desativa(self, client: TestClient, recepcao: User) -> None:
        """Desativar serviço mexe no que o studio vende: é da proprietária."""
        t = login(client, recepcao.email)
        sid = client.post("/api/v1/services", json=mensalidade(), headers=auth(t)).json()["id"]

        r = client.delete(f"/api/v1/services/{sid}", headers=auth(t))

        assert r.status_code == 403

    def test_admin_desativa(self, client: TestClient, admin: User) -> None:
        t = login(client, admin.email)
        sid = client.post("/api/v1/services", json=mensalidade(), headers=auth(t)).json()["id"]

        r = client.delete(f"/api/v1/services/{sid}", headers=auth(t))

        assert r.status_code == 200
        assert r.json()["ativo"] is False


def test_servico_inativo_some_da_listagem(client: TestClient, admin: User) -> None:
    t = login(client, admin.email)
    sid = client.post("/api/v1/services", json=mensalidade(), headers=auth(t)).json()["id"]
    client.delete(f"/api/v1/services/{sid}", headers=auth(t))

    padrao = client.get("/api/v1/services", headers=auth(t))
    todos = client.get("/api/v1/services", params={"incluir_inativos": True}, headers=auth(t))

    assert len(padrao.json()) == 0
    assert len(todos.json()) == 1
