from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.user import Papel, User

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

CREDENCIAIS_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não foi possível validar as credenciais",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve o usuário autenticado a partir do token.

    O papel é relido do banco, e não do payload: se alguém for rebaixado ou
    desativado, o token emitido antes não pode continuar valendo até expirar.
    Com token de 12 horas isso seria meio dia de acesso indevido.
    """
    try:
        payload = decodificar_token(token)
    except jwt.PyJWTError as exc:
        raise CREDENCIAIS_INVALIDAS from exc

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise CREDENCIAIS_INVALIDAS

    try:
        user_id = int(subject)
    except ValueError as exc:
        raise CREDENCIAIS_INVALIDAS from exc

    user = db.get(User, user_id)
    if user is None:
        raise CREDENCIAIS_INVALIDAS
    if not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_papel(*papeis: Papel) -> Callable[[User], User]:
    """Restringe uma rota aos papéis informados.

    Uso:
        @router.get("/", dependencies=[Depends(require_papel(Papel.ADMIN))])

    Retorna 403 (autenticado, mas sem permissão), não 401 (não autenticado).
    A distinção importa para o frontend: 401 manda para a tela de login,
    403 mostra "acesso negado".
    """
    permitidos = set(papeis)

    def _verificar(user: CurrentUser) -> User:
        if user.papel not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seu perfil não tem permissão para esta operação",
            )
        return user

    return _verificar
