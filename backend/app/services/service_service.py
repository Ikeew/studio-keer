from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


def _garantir_nome_livre(db: Session, nome: str, excluindo_id: int | None = None) -> None:
    stmt = select(Service).where(func.lower(Service.nome) == nome.lower())
    if excluindo_id is not None:
        stmt = stmt.where(Service.id != excluindo_id)
    if db.execute(stmt).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe um serviço chamado '{nome}'",
        )


def buscar(db: Session, service_id: int) -> Service:
    servico = db.get(Service, service_id)
    if servico is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serviço não encontrado")
    return servico


def listar(db: Session, *, incluir_inativos: bool = False) -> list[Service]:
    stmt = select(Service).order_by(Service.nome)
    if not incluir_inativos:
        stmt = stmt.where(Service.ativo.is_(True))
    return list(db.execute(stmt).scalars().all())


def criar(db: Session, dados: ServiceCreate) -> Service:
    _garantir_nome_livre(db, dados.nome)
    servico = Service(**dados.model_dump())
    db.add(servico)
    db.flush()
    return servico


def atualizar(db: Session, service_id: int, dados: ServiceUpdate) -> Service:
    servico = buscar(db, service_id)
    _garantir_nome_livre(db, dados.nome, excluindo_id=service_id)

    for campo, valor in dados.model_dump().items():
        setattr(servico, campo, valor)

    db.flush()
    return servico


def desativar(db: Session, service_id: int) -> Service:
    """Exclusão lógica: sessões e cobranças antigas apontam para o serviço."""
    servico = buscar(db, service_id)
    servico.ativo = False
    db.flush()
    return servico
