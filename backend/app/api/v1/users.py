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
    "/users",
    response_model=list[UserRead],
    # Só a proprietária administra usuários. Recepção e instrutor recebem 403.
    dependencies=[Depends(require_papel(Papel.ADMIN))],
)
def listar_usuarios(db: Annotated[Session, Depends(get_db)]) -> list[UserRead]:
    users = db.execute(select(User).order_by(User.nome)).scalars().all()
    return [UserRead.model_validate(u) for u in users]
