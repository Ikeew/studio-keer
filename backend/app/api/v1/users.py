from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_papel
from app.db.session import get_db
from app.models.user import Papel, User
from app.schemas.user import UserRead

router = APIRouter()


@router.get(
    "/instrutores",
    response_model=list[UserRead],
    # Recepção e admin: a recepção precisa escolher o instrutor ao criar uma
    # turma, e /users é restrita ao admin. Esta rota devolve SÓ quem pode
    # ministrar, e não é caminho para administrar usuários.
    dependencies=[Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))],
)
def listar_instrutores(db: Annotated[Session, Depends(get_db)]) -> list[UserRead]:
    users = (
        db.execute(
            select(User)
            .where(
                User.ativo.is_(True),
                User.papel.in_([Papel.INSTRUTOR, Papel.ADMIN]),
            )
            .order_by(User.nome)
        )
        .scalars()
        .all()
    )
    return [UserRead.model_validate(u) for u in users]


@router.get(
    "/users",
    response_model=list[UserRead],
    # Só a proprietária administra usuários. Recepção e instrutor recebem 403.
    dependencies=[Depends(require_papel(Papel.ADMIN))],
)
def listar_usuarios(db: Annotated[Session, Depends(get_db)]) -> list[UserRead]:
    users = db.execute(select(User).order_by(User.nome)).scalars().all()
    return [UserRead.model_validate(u) for u in users]
