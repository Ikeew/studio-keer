from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import criar_access_token
from app.models.user import User
from tests.conftest import auth, login


class TestPermissaoPorPapel:
    """`/users` é restrita ao admin. Serve de caso concreto do RBAC."""

    def test_admin_tem_acesso(self, client: TestClient, admin: User) -> None:
        token = login(client, admin.email)

        r = client.get("/api/v1/users", headers=auth(token))

        assert r.status_code == 200
        assert any(u["email"] == admin.email for u in r.json())

    def test_recepcao_recebe_403(self, client: TestClient, recepcao: User) -> None:
        token = login(client, recepcao.email)

        r = client.get("/api/v1/users", headers=auth(token))

        assert r.status_code == 403

    def test_instrutor_recebe_403(self, client: TestClient, instrutor: User) -> None:
        token = login(client, instrutor.email)

        r = client.get("/api/v1/users", headers=auth(token))

        assert r.status_code == 403

    def test_sem_token_recebe_401_e_nao_403(self, client: TestClient) -> None:
        """401 e 403 significam coisas diferentes para o frontend:
        401 manda para o login, 403 mostra "acesso negado"."""
        r = client.get("/api/v1/users")

        assert r.status_code == 401

    def test_papel_forjado_no_token_nao_da_acesso(
        self, client: TestClient, db: Session, recepcao: User
    ) -> None:
        """Defesa central do RBAC.

        O token traz `papel` no payload, mas a autorização consulta o banco.
        Um token assinado com papel de admin para um usuário que é recepção
        não pode abrir a rota de admin — senão bastaria vazar a SECRET_KEY,
        ou um bug de emissão, para escalar privilégio.
        """
        forjado = criar_access_token(subject=str(recepcao.id), papel="admin")

        r = client.get("/api/v1/users", headers=auth(forjado))

        assert r.status_code == 403


class TestListaDeInstrutores:
    """A recepção precisa escolher o instrutor ao criar uma turma.

    `/users` é do admin; `/instrutores` existe para esse caso e devolve só
    quem pode ministrar.
    """

    def test_recepcao_lista_instrutores(
        self, client: TestClient, recepcao: User, instrutor: User
    ) -> None:
        token = login(client, recepcao.email)

        r = client.get("/api/v1/instrutores", headers=auth(token))

        assert r.status_code == 200
        assert any(u["email"] == instrutor.email for u in r.json())

    def test_nao_devolve_a_recepcao_como_instrutor(
        self, client: TestClient, recepcao: User, instrutor: User
    ) -> None:
        token = login(client, recepcao.email)

        r = client.get("/api/v1/instrutores", headers=auth(token))

        assert all(u["papel"] != "recepcao" for u in r.json())

    def test_instrutor_nao_acessa(self, client: TestClient, instrutor: User) -> None:
        token = login(client, instrutor.email)

        assert client.get("/api/v1/instrutores", headers=auth(token)).status_code == 403
