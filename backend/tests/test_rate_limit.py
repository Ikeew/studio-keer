"""Limite de tentativas de login.

Dois níveis, de propósito:

- Os testes de HTTP cobrem o contrato que o frontend e um atacante veem:
  status, mensagem, cabeçalho, e quem trava quem.
- Os testes de `_Contador` cobrem a janela deslizante com o tempo passado na
  mão. O contador recebe `agora` como argumento justamente para isso: dá para
  testar "quinze minutos depois" sem mexer no relógio do processo, que é o
  tipo de manipulação que contamina teste vizinho.
"""

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ratelimit import _Contador, _identificador_de_conta
from app.models.user import Papel, User
from tests.conftest import SENHA_PADRAO, criar_usuario

settings = get_settings()

LOGIN = "/api/v1/auth/login"


def tentar(
    client: TestClient,
    email: str,
    senha: str = "senha-errada",
    ip: str = "203.0.113.7",
) -> Response:
    """Uma tentativa de login vinda de um IP específico.

    O `X-Forwarded-For` é o que a app lê em produção, atrás do proxy do
    Render — mandar aqui é reproduzir a condição real, não driblar o teste.
    """
    return client.post(
        LOGIN,
        data={"username": email, "password": senha},
        headers={"X-Forwarded-For": ip},
    )


class TestBloqueioPorConta:
    def test_sexta_tentativa_e_recusada_com_429(
        self, client: TestClient, recepcao: User
    ) -> None:
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            assert tentar(client, recepcao.email).status_code == 401

        r = tentar(client, recepcao.email)

        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert int(r.headers["Retry-After"]) > 0
        assert "tentativas" in r.json()["detail"].lower()

    def test_senha_certa_nao_destrava_conta_bloqueada(
        self, client: TestClient, recepcao: User
    ) -> None:
        """O bloqueio precisa valer mesmo para quem acerta.

        Se a senha correta passasse, o limite não protegeria de nada: o
        atacante que acerta na tentativa 400 entra do mesmo jeito. O preço é
        a recepcionista esperar quinze minutos depois de errar cinco vezes —
        e é esse o preço que estamos escolhendo pagar.
        """
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            tentar(client, recepcao.email)

        r = tentar(client, recepcao.email, senha=SENHA_PADRAO)

        assert r.status_code == 429

    def test_login_certo_zera_o_contador(self, client: TestClient, recepcao: User) -> None:
        """Quem errou, corrigiu e entrou volta com a cota cheia.

        Sem isto, errar duas vezes hoje de manhã e três à tarde bloquearia a
        conta sem que nada de anormal tivesse acontecido.
        """
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA - 1):
            tentar(client, recepcao.email)

        assert tentar(client, recepcao.email, senha=SENHA_PADRAO).status_code == 200

        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA - 1):
            assert tentar(client, recepcao.email).status_code == 401

    def test_insistir_durante_o_bloqueio_nao_estende_o_prazo(
        self, client: TestClient, recepcao: User
    ) -> None:
        """O bloqueio é defesa, não arma.

        Se cada tentativa recusada reiniciasse o relógio, quem soubesse o
        e-mail da recepção poderia mantê-la fora do sistema o dia inteiro,
        martelando o login de fora. O endpoint recusa sem contar a tentativa,
        então o prazo só corre para frente.
        """
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            tentar(client, recepcao.email)

        primeira = int(tentar(client, recepcao.email).headers["Retry-After"])
        for _ in range(10):
            tentar(client, recepcao.email)
        ultima = int(tentar(client, recepcao.email).headers["Retry-After"])

        assert ultima <= primeira

    def test_conta_inexistente_tambem_conta(self, client: TestClient) -> None:
        """Senão bastaria alternar entre um e-mail real e um inventado."""
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            assert tentar(client, "ninguem@example.com").status_code == 401

        assert tentar(client, "ninguem@example.com").status_code == 429

    def test_bloqueio_nao_revela_se_a_conta_existe(
        self, client: TestClient, recepcao: User
    ) -> None:
        """Conta real e conta inventada precisam responder igual.

        A resposta 429 é observável sem credencial nenhuma. Se ela fosse
        diferente para e-mail cadastrado, viraria justamente o oráculo de
        enumeração que o 401 genérico de `auth_service.autenticar` evita.
        """
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            tentar(client, recepcao.email)
            tentar(client, "ninguem@example.com")

        real = tentar(client, recepcao.email)
        inventada = tentar(client, "ninguem@example.com")

        assert real.status_code == inventada.status_code == 429
        assert real.json()["detail"] == inventada.json()["detail"]

    def test_email_com_caixa_diferente_conta_junto(
        self, client: TestClient, recepcao: User
    ) -> None:
        """`Maria@` e `maria@` são a mesma conta no login, e no limite também."""
        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            tentar(client, recepcao.email.upper())

        assert tentar(client, recepcao.email).status_code == 429


class TestIsolamentoEntreContas:
    def test_conta_bloqueada_nao_derruba_as_outras_do_mesmo_ip(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """O caso que motivou contar por conta em vez de por IP.

        Recepção, proprietária e instrutores dividem o roteador da sala. Se o
        bloqueio fosse por IP, a recepcionista errando a senha na segunda de
        manhã derrubaria o login do studio inteiro, no pico do movimento.
        """
        outra = criar_usuario(db, Papel.ADMIN, email="proprietaria@example.com")

        for _ in range(settings.LOGIN_MAX_TENTATIVAS_CONTA):
            tentar(client, recepcao.email)
        assert tentar(client, recepcao.email).status_code == 429

        r = tentar(client, outra.email, senha=SENHA_PADRAO)

        assert r.status_code == 200


class TestBloqueioPorOrigem:
    def test_varredura_de_muitas_contas_bloqueia_o_ip(self, client: TestClient) -> None:
        """O ataque que a contagem por conta não enxerga.

        Uma senha provável contra cem e-mails diferentes nunca chega a cinco
        falhas em conta nenhuma. Quem repete o padrão é a origem.
        """
        for i in range(settings.LOGIN_MAX_TENTATIVAS_IP):
            assert tentar(client, f"alvo{i}@example.com").status_code == 401

        r = tentar(client, "mais-um@example.com")

        assert r.status_code == 429

    def test_origens_diferentes_contam_separado(self, client: TestClient) -> None:
        for i in range(settings.LOGIN_MAX_TENTATIVAS_IP):
            tentar(client, f"alvo{i}@example.com", ip="203.0.113.7")
        assert tentar(client, "outro@example.com", ip="203.0.113.7").status_code == 429

        r = tentar(client, "outro@example.com", ip="198.51.100.4")

        assert r.status_code == 401


class TestJanelaDeslizante:
    """O contador direto, com o tempo passado na mão."""

    def _contador(self) -> _Contador:
        return _Contador(maximo=3, janela_s=900, bloqueio_s=900)

    def test_falhas_dentro_da_janela_bloqueiam(self) -> None:
        c = self._contador()
        for t in (0.0, 10.0, 20.0):
            c.registrar("chave", t)

        assert c.bloqueio("chave", 20.0) > 0

    def test_falha_velha_sai_da_janela(self) -> None:
        """Errar uma vez de manhã não pode contar contra a noite."""
        c = self._contador()
        c.registrar("chave", 0.0)
        c.registrar("chave", 10.0)
        c.registrar("chave", 1000.0)  # a primeira já saiu da janela de 900s

        assert c.bloqueio("chave", 1000.0) == 0

    def test_bloqueio_expira(self) -> None:
        c = self._contador()
        for t in (0.0, 1.0, 2.0):
            c.registrar("chave", t)
        assert c.bloqueio("chave", 2.0) > 0

        assert c.bloqueio("chave", 903.0) == 0

    def test_limpar_libera_a_chave(self) -> None:
        c = self._contador()
        for t in (0.0, 1.0, 2.0):
            c.registrar("chave", t)

        c.limpar("chave")

        assert c.bloqueio("chave", 2.0) == 0


class TestIdentificadorDeConta:
    def test_nao_contem_o_email(self) -> None:
        """O log registra este identificador, e logs.py proíbe e-mail."""
        assert "maria@example.com" not in _identificador_de_conta("maria@example.com")

    def test_e_estavel_e_normaliza(self) -> None:
        assert _identificador_de_conta(" Maria@Example.com ") == _identificador_de_conta(
            "maria@example.com"
        )
