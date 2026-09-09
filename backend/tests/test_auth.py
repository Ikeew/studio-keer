from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import criar_access_token
from app.models.user import Papel, User
from tests.conftest import SENHA_PADRAO, auth, criar_usuario, login


class TestLogin:
    def test_login_valido_devolve_token_e_usuario(self, client: TestClient, recepcao: User) -> None:
        r = client.post(
            "/api/v1/auth/login",
            data={"username": recepcao.email, "password": SENHA_PADRAO},
        )

        assert r.status_code == 200
        corpo = r.json()
        assert corpo["token_type"] == "bearer"
        assert corpo["access_token"]
        assert corpo["usuario"]["email"] == recepcao.email
        assert corpo["usuario"]["papel"] == "recepcao"

    def test_login_nao_vaza_hash_da_senha(self, client: TestClient, recepcao: User) -> None:
        r = client.post(
            "/api/v1/auth/login",
            data={"username": recepcao.email, "password": SENHA_PADRAO},
        )

        assert "senha_hash" not in r.text
        assert "senha" not in r.json()["usuario"]

    def test_senha_errada_recusa(self, client: TestClient, recepcao: User) -> None:
        r = client.post(
            "/api/v1/auth/login",
            data={"username": recepcao.email, "password": "senha-errada"},
        )

        assert r.status_code == 401

    def test_email_inexistente_recusa(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/auth/login",
            data={"username": "ninguem@example.com", "password": SENHA_PADRAO},
        )

        assert r.status_code == 401

    def test_mesma_mensagem_para_email_inexistente_e_senha_errada(
        self, client: TestClient, recepcao: User
    ) -> None:
        """Mensagens distintas revelariam quais e-mails têm conta no sistema."""
        senha_errada = client.post(
            "/api/v1/auth/login",
            data={"username": recepcao.email, "password": "outra-coisa"},
        )
        inexistente = client.post(
            "/api/v1/auth/login",
            data={"username": "ninguem@example.com", "password": SENHA_PADRAO},
        )

        assert senha_errada.json() == inexistente.json()

    def test_email_e_case_insensitive(self, client: TestClient, db: Session) -> None:
        criar_usuario(db, Papel.RECEPCAO, email="maria@studiokeer.com.br")

        r = client.post(
            "/api/v1/auth/login",
            data={"username": "Maria@StudioKeer.com.BR", "password": SENHA_PADRAO},
        )

        assert r.status_code == 200

    def test_usuario_desativado_nao_entra(self, client: TestClient, db: Session) -> None:
        desligado = criar_usuario(db, Papel.RECEPCAO, email="ex@example.com", ativo=False)

        r = client.post(
            "/api/v1/auth/login",
            data={"username": desligado.email, "password": SENHA_PADRAO},
        )

        assert r.status_code == 401


class TestTokenInvalido:
    def test_sem_token_e_401(self, client: TestClient) -> None:
        r = client.get("/api/v1/auth/me")

        assert r.status_code == 401

    def test_token_expirado_e_401(self, client: TestClient, recepcao: User) -> None:
        expirado = criar_access_token(
            subject=str(recepcao.id),
            papel=recepcao.papel.value,
            expires_delta=timedelta(minutes=-5),
        )

        r = client.get("/api/v1/auth/me", headers=auth(expirado))

        assert r.status_code == 401

    def test_token_com_assinatura_adulterada_e_401(
        self, client: TestClient, recepcao: User
    ) -> None:
        token = login(client, recepcao.email)
        # Corrompe o último caractere: o payload continua legível, mas a
        # assinatura não confere mais.
        adulterado = token[:-1] + ("a" if token[-1] != "a" else "b")

        r = client.get("/api/v1/auth/me", headers=auth(adulterado))

        assert r.status_code == 401

    def test_token_de_usuario_inexistente_e_401(self, client: TestClient) -> None:
        orfao = criar_access_token(subject="99999", papel="admin")

        r = client.get("/api/v1/auth/me", headers=auth(orfao))

        assert r.status_code == 401

    def test_lixo_no_header_e_401(self, client: TestClient) -> None:
        r = client.get("/api/v1/auth/me", headers=auth("isto-nao-e-um-jwt"))

        assert r.status_code == 401


class TestMe:
    def test_me_devolve_o_usuario_do_token(self, client: TestClient, instrutor: User) -> None:
        token = login(client, instrutor.email)

        r = client.get("/api/v1/auth/me", headers=auth(token))

        assert r.status_code == 200
        assert r.json()["email"] == instrutor.email
        assert r.json()["papel"] == "instrutor"

    def test_desativar_usuario_invalida_token_ja_emitido(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """O papel e o estado vêm do banco, não do payload do token.

        Sem isso, desligar alguém deixaria o token dele valendo por até 12
        horas — o tempo de expiração configurado.
        """
        token = login(client, recepcao.email)
        assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200

        recepcao.ativo = False
        db.flush()

        r = client.get("/api/v1/auth/me", headers=auth(token))

        assert r.status_code == 403
