from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_papel
from app.db.session import get_db
from app.models.user import Papel, User
from app.schemas.user import PaginaDeUsuarios, UserRead

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
    response_model=PaginaDeUsuarios,
    # Só a proprietária administra usuários. Recepção e instrutor recebem 403.
    dependencies=[Depends(require_papel(Papel.ADMIN))],
)
def listar_usuarios(
    db: Annotated[Session, Depends(get_db)],
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginaDeUsuarios:
    # A equipe do studio são cinco pessoas, então uma página basta. O envelope
    # está aqui pela mesma razão do catálogo de serviços: listagem que responde
    # em formato próprio é a que alguém esquece de paginar quando cresce.
    base = select(User)
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    users = (
        db.execute(base.order_by(User.nome).offset((pagina - 1) * tamanho).limit(tamanho))
        .scalars()
        .all()
    )
    return PaginaDeUsuarios(
        itens=[UserRead.model_validate(u) for u in users],
        total=total,
        pagina=pagina,
        tamanho=tamanho,
    )
