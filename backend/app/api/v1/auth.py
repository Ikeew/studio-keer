from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import CurrentUser
from app.core.ratelimit import (
    identificar_origem,
    obter_limitador,
    registrar_bloqueio_no_log,
)
from app.core.security import criar_access_token
from app.db.session import get_db
from app.schemas.auth import Token
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter()
settings = get_settings()


@router.post("/auth/login", response_model=Token)
def login(
    # OAuth2PasswordRequestForm (form-urlencoded, campo `username`) em vez de
    # JSON: é o que faz o botão "Authorize" do /docs funcionar, e a equipe
    # testa a API por lá. O campo `username` recebe o e-mail.
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
) -> Token:
    limitador = obter_limitador()
    origem = identificar_origem(request)

    # Verificado ANTES de consultar o banco: uma conta em bloqueio não deve
    # custar uma query nem uma verificação de bcrypt por tentativa — é
    # justamente esse custo que um ataque de força bruta procura.
    bloqueio = limitador.verificar(email=form.username, ip=origem)
    if bloqueio is not None:
        registrar_bloqueio_no_log(bloqueio, email=form.username, ip=origem)
        minutos = max(1, round(bloqueio.segundos_restantes / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Muitas tentativas de login. Tente de novo em {minutos} "
                f"minuto{'s' if minutos > 1 else ''}."
            ),
            headers={"Retry-After": str(bloqueio.segundos_restantes)},
        )

    user = auth_service.autenticar(db, form.username, form.password)
    if user is None:
        limitador.registrar_falha(email=form.username, ip=origem)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limitador.registrar_sucesso(email=form.username)
    token = criar_access_token(subject=str(user.id), papel=user.papel.value)
    return Token(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        usuario=UserRead.model_validate(user),
    )


@router.get("/auth/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    """Quem sou eu. O frontend chama no boot para restaurar a sessão."""
    return UserRead.model_validate(user)
