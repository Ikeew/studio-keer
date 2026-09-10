from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services import service_service

router = APIRouter(prefix="/services", tags=["serviços"])

DbSession = Annotated[Session, Depends(get_db)]

SO_OPERADORES = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))


@router.get("", response_model=list[ServiceRead], dependencies=[SO_OPERADORES])
def listar(db: DbSession, incluir_inativos: bool = False) -> list[ServiceRead]:
    servicos = service_service.listar(db, incluir_inativos=incluir_inativos)
    return [ServiceRead.model_validate(s) for s in servicos]


@router.get("/{service_id}", response_model=ServiceRead, dependencies=[SO_OPERADORES])
def obter(service_id: int, db: DbSession) -> ServiceRead:
    return ServiceRead.model_validate(service_service.buscar(db, service_id))


@router.post(
    "",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[SO_OPERADORES],
)
def criar(dados: ServiceCreate, db: DbSession) -> ServiceRead:
    servico = service_service.criar(db, dados)
    db.commit()
    return ServiceRead.model_validate(servico)


@router.put("/{service_id}", response_model=ServiceRead, dependencies=[SO_OPERADORES])
def atualizar(service_id: int, dados: ServiceUpdate, db: DbSession) -> ServiceRead:
    servico = service_service.atualizar(db, service_id, dados)
    db.commit()
    return ServiceRead.model_validate(servico)


@router.delete(
    "/{service_id}",
    response_model=ServiceRead,
    # Desativar serviço é decisão da proprietária: mexe no que o studio
    # vende e no que aparece na agenda.
    dependencies=[Depends(require_papel(Papel.ADMIN))],
)
def desativar(service_id: int, db: DbSession) -> ServiceRead:
    servico = service_service.desativar(db, service_id)
    db.commit()
    return ServiceRead.model_validate(servico)
