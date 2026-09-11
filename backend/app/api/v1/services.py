from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.service import (
    PaginaDeServicos,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)
from app.services import service_service

router = APIRouter(prefix="/services", tags=["serviços"])

DbSession = Annotated[Session, Depends(get_db)]

SO_OPERADORES = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))


@router.get("", response_model=PaginaDeServicos, dependencies=[SO_OPERADORES])
def listar(
    db: DbSession,
    incluir_inativos: bool = False,
    # Mesmos limites das outras listagens — ver api/v1/patients.py. O padrão
    # de 50 cabe o catálogo inteiro do studio numa página só, então as telas
    # que usam serviço como opção de select continuam recebendo tudo.
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginaDeServicos:
    itens, total = service_service.listar(
        db, incluir_inativos=incluir_inativos, pagina=pagina, tamanho=tamanho
    )
    return PaginaDeServicos(
        itens=[ServiceRead.model_validate(s) for s in itens],
        total=total,
        pagina=pagina,
        tamanho=tamanho,
    )


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
