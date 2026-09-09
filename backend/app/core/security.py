from datetime import UTC, datetime, timedelta
from typing import cast

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# O bcrypt trunca a senha em 72 bytes. Validamos no schema de entrada para o
# usuário receber um erro claro em vez de uma truncagem silenciosa — que faria
# duas senhas diferentes com o mesmo prefixo abrirem a mesma conta.
BCRYPT_MAX_BYTES = 72


def hash_senha(senha: str) -> str:
    # cast porque o passlib não tem stubs de tipo e devolve Any.
    return cast(str, pwd_context.hash(senha))


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return cast(bool, pwd_context.verify(senha, senha_hash))


def criar_access_token(*, subject: str, papel: str, expires_delta: timedelta | None = None) -> str:
    """Gera o JWT de acesso.

    `sub` carrega o id do usuário e `papel` evita uma consulta ao banco em
    toda checagem de permissão. O papel ainda é reconferido contra o banco em
    `get_current_user`: se alguém for rebaixado ou desativado, o token antigo
    não pode continuar valendo até expirar.
    """
    expira = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "papel": papel,
        "exp": expira,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> dict[str, object]:
    """Decodifica e valida o JWT.

    Levanta `jwt.PyJWTError` (incluindo `ExpiredSignatureError`) se o token
    for inválido, expirado ou assinado com outra chave.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
