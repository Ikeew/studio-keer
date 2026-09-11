from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User
from tests.conftest import auth, login

CPF_VALIDO = "529.982.247-25"
OUTRO_CPF = "111.444.777-35"


def novo(**extra: object) -> dict[str, object]:
    base: dict[str, object] = {"nome_completo": "Maria Silva"}
    base.update(extra)
    return base


class TestCriar:
    def test_cria_paciente_minimo(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(), headers=auth(t))

        assert r.status_code == 201
        assert r.json()["nome_completo"] == "Maria Silva"
        assert r.json()["ativo"] is True

    def test_normaliza_espacos_do_nome(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json=novo(nome_completo="  Ana   Costa  "),
            headers=auth(t),
        )

        assert r.json()["nome_completo"] == "Ana Costa"

    def test_guarda_cpf_sem_pontuacao_e_devolve_formatado(
        self, client: TestClient, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(cpf=CPF_VALIDO), headers=auth(t))

        assert r.json()["cpf"] == "52998224725"
        assert r.json()["cpf_formatado"] == CPF_VALIDO

    def test_recusa_cpf_invalido(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(cpf="111.111.111-11"), headers=auth(t))

        assert r.status_code == 422

    def test_cpf_e_opcional(self, client: TestClient, recepcao: User) -> None:
        """A recepção nem sempre tem o CPF na hora do cadastro."""
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(cpf=None), headers=auth(t))

        assert r.status_code == 201
        assert r.json()["cpf"] is None

    def test_cpf_duplicado_da_409_com_nome_do_titular(
        self, client: TestClient, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)
        client.post("/api/v1/patients", json=novo(cpf=CPF_VALIDO), headers=auth(t))

        r = client.post(
            "/api/v1/patients",
            json=novo(nome_completo="Outra Pessoa", cpf=CPF_VALIDO),
            headers=auth(t),
        )

        assert r.status_code == 409
        assert "Maria Silva" in r.json()["detail"]

    def test_varios_pacientes_sem_cpf_convivem(self, client: TestClient, recepcao: User) -> None:
        """O índice único é parcial: 'sem CPF' não colide com 'sem CPF'."""
        t = login(client, recepcao.email)

        a = client.post("/api/v1/patients", json=novo(nome_completo="Um Sem Cpf"), headers=auth(t))
        b = client.post(
            "/api/v1/patients", json=novo(nome_completo="Dois Sem Cpf"), headers=auth(t)
        )

        assert a.status_code == 201
        assert b.status_code == 201

    def test_recusa_nascimento_no_futuro(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json=novo(data_nascimento="2099-01-01"),
            headers=auth(t),
        )

        assert r.status_code == 422

    def test_contato_de_emergencia(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post(
            "/api/v1/patients",
            json=novo(emergencia_nome="João Silva", emergencia_telefone="11988887777"),
            headers=auth(t),
        )

        assert r.json()["emergencia_nome"] == "João Silva"


class TestConsentimentoLGPD:
    def test_consentimento_carimba_a_data(self, client: TestClient, recepcao: User) -> None:
        """Sem a data, o consentimento não é comprovável."""
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(consentimento_lgpd=True), headers=auth(t))

        assert r.json()["consentimento_lgpd"] is True
        assert r.json()["consentimento_em"] == date.today().isoformat()

    def test_sem_consentimento_nao_tem_data(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(), headers=auth(t))

        assert r.json()["consentimento_em"] is None

    def test_retirar_consentimento_limpa_a_data(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        pid = client.post(
            "/api/v1/patients", json=novo(consentimento_lgpd=True), headers=auth(t)
        ).json()["id"]

        r = client.patch(
            f"/api/v1/patients/{pid}", json={"consentimento_lgpd": False}, headers=auth(t)
        )

        assert r.json()["consentimento_lgpd"] is False
        assert r.json()["consentimento_em"] is None


class TestIdadeDerivada:
    def test_idade_vem_da_data_de_nascimento(self, client: TestClient, recepcao: User) -> None:
        """Idade é derivada, nunca coluna — coluna erra no dia do aniversário."""
        t = login(client, recepcao.email)
        hoje = date.today()
        nascimento = date(hoje.year - 30, hoje.month, hoje.day)

        r = client.post(
            "/api/v1/patients",
            json=novo(data_nascimento=nascimento.isoformat()),
            headers=auth(t),
        )

        assert r.json()["idade"] == 30

    def test_idade_e_nula_sem_data(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.post("/api/v1/patients", json=novo(), headers=auth(t))

        assert r.json()["idade"] is None


class TestBuscaEPaginacao:
    def _semear(self, client: TestClient, t: str) -> None:
        for nome, tel in [
            ("Maria Silva", "(11) 98765-4321"),
            ("João Santos", "(11) 98765-4322"),
            ("Ana Costa", "(21) 97777-1111"),
        ]:
            client.post(
                "/api/v1/patients", json=novo(nome_completo=nome, telefone=tel), headers=auth(t)
            )

    def test_busca_por_nome_ignora_maiusculas(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        self._semear(client, t)

        r = client.get("/api/v1/patients", params={"busca": "maria"}, headers=auth(t))

        assert r.json()["total"] == 1
        assert r.json()["itens"][0]["nome_completo"] == "Maria Silva"

    def test_busca_por_telefone_ignora_a_mascara(self, client: TestClient, recepcao: User) -> None:
        """A recepção digita com máscara; o banco guarda como veio."""
        t = login(client, recepcao.email)
        self._semear(client, t)

        r = client.get("/api/v1/patients", params={"busca": "11987654321"}, headers=auth(t))

        assert r.json()["total"] == 1
        assert r.json()["itens"][0]["nome_completo"] == "Maria Silva"

    def test_pagina_devolve_total_e_recorte(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        self._semear(client, t)

        r = client.get("/api/v1/patients", params={"tamanho": 2, "pagina": 1}, headers=auth(t))

        assert r.json()["total"] == 3
        assert len(r.json()["itens"]) == 2

    def test_ordena_por_nome(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        self._semear(client, t)

        r = client.get("/api/v1/patients", headers=auth(t))

        nomes = [i["nome_completo"] for i in r.json()["itens"]]
        assert nomes == sorted(nomes)

    def test_segunda_pagina_nao_repete_a_primeira(
        self, client: TestClient, recepcao: User
    ) -> None:
        """Recorte sem sobreposição é o que faz a paginação valer.

        Com OFFSET errado por um, um paciente apareceria em duas páginas e
        outro em nenhuma — e ninguém percebe olhando uma página de cada vez.
        """
        t = login(client, recepcao.email)
        self._semear(client, t)

        p1 = client.get("/api/v1/patients", params={"tamanho": 2, "pagina": 1}, headers=auth(t))
        p2 = client.get("/api/v1/patients", params={"tamanho": 2, "pagina": 2}, headers=auth(t))

        ids1 = {i["id"] for i in p1.json()["itens"]}
        ids2 = {i["id"] for i in p2.json()["itens"]}
        assert len(ids2) == 1
        assert ids1.isdisjoint(ids2)

    def test_pagina_alem_do_fim_devolve_vazio_com_total(
        self, client: TestClient, recepcao: User
    ) -> None:
        """Total continua correto: a tela precisa dele para montar o paginador."""
        t = login(client, recepcao.email)
        self._semear(client, t)

        r = client.get("/api/v1/patients", params={"tamanho": 2, "pagina": 50}, headers=auth(t))

        assert r.json()["itens"] == []
        assert r.json()["total"] == 3


class TestLimitesDaListagem:
    """Limites de entrada da listagem.

    Não é paranoia com atacante: a rota exige token de recepção ou admin. É
    que um parâmetro absurdo chegando por engano — link velho, teste, dedo
    escorregando no zero — vira trabalho pesado no banco sem devolver nada.
    Recusar na borda é mais barato que descobrir no log de lentidão.
    """

    def test_tamanho_acima_do_teto_e_recusado(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"tamanho": 5000}, headers=auth(t))

        assert r.status_code == 422

    def test_tamanho_zero_ou_negativo_e_recusado(
        self, client: TestClient, recepcao: User
    ) -> None:
        t = login(client, recepcao.email)

        for tamanho in (0, -1):
            r = client.get("/api/v1/patients", params={"tamanho": tamanho}, headers=auth(t))
            assert r.status_code == 422

    def test_pagina_absurda_e_recusada(self, client: TestClient, recepcao: User) -> None:
        """`pagina=999999999` viraria um OFFSET que o banco percorre à toa."""
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"pagina": 999_999_999}, headers=auth(t))

        assert r.status_code == 422

    def test_busca_longa_demais_e_recusada(self, client: TestClient, recepcao: User) -> None:
        """O termo cai num índice trigram; um parágrafo ali é só custo."""
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"busca": "a" * 5000}, headers=auth(t))

        assert r.status_code == 422

    def test_busca_no_limite_passa(self, client: TestClient, recepcao: User) -> None:
        """O teto não pode cortar um nome real — cem caracteres sobram."""
        t = login(client, recepcao.email)

        r = client.get("/api/v1/patients", params={"busca": "a" * 100}, headers=auth(t))

        assert r.status_code == 200


class TestSoftDelete:
    def test_desativar_nao_apaga(self, client: TestClient, db: Session, recepcao: User) -> None:
        t = login(client, recepcao.email)
        pid = client.post("/api/v1/patients", json=novo(), headers=auth(t)).json()["id"]

        r = client.delete(f"/api/v1/patients/{pid}", headers=auth(t))

        assert r.status_code == 200
        assert r.json()["ativo"] is False
        assert db.get(Patient, pid) is not None, "o registro tem de continuar existindo"

    def test_inativo_some_da_listagem_padrao(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        pid = client.post("/api/v1/patients", json=novo(), headers=auth(t)).json()["id"]
        client.delete(f"/api/v1/patients/{pid}", headers=auth(t))

        padrao = client.get("/api/v1/patients", headers=auth(t))
        com_inativos = client.get(
            "/api/v1/patients", params={"incluir_inativos": True}, headers=auth(t)
        )

        assert padrao.json()["total"] == 0
        assert com_inativos.json()["total"] == 1

    def test_reativar(self, client: TestClient, recepcao: User) -> None:
        t = login(client, recepcao.email)
        pid = client.post("/api/v1/patients", json=novo(), headers=auth(t)).json()["id"]
        client.delete(f"/api/v1/patients/{pid}", headers=auth(t))

        r = client.post(f"/api/v1/patients/{pid}/reativar", headers=auth(t))

        assert r.json()["ativo"] is True


class TestPermissoes:
    def test_instrutor_nao_acessa_pacientes(self, client: TestClient, instrutor: User) -> None:
        """O instrutor lê a agenda do dia, não a ficha do paciente."""
        t = login(client, instrutor.email)

        assert client.get("/api/v1/patients", headers=auth(t)).status_code == 403
        assert client.post("/api/v1/patients", json=novo(), headers=auth(t)).status_code == 403

    def test_admin_e_recepcao_acessam(
        self, client: TestClient, admin: User, recepcao: User
    ) -> None:
        for user in (admin, recepcao):
            t = login(client, user.email)
            assert client.get("/api/v1/patients", headers=auth(t)).status_code == 200

    def test_sem_token_e_401(self, client: TestClient) -> None:
        assert client.get("/api/v1/patients").status_code == 401


def test_paciente_inexistente_da_404(client: TestClient, recepcao: User) -> None:
    t = login(client, recepcao.email)

    assert client.get("/api/v1/patients/99999", headers=auth(t)).status_code == 404
