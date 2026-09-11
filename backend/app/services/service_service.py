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


def listar(
    db: Session,
    *,
    incluir_inativos: bool = False,
    pagina: int = 1,
    tamanho: int = 50,
) -> tuple[list[Service], int]:
    """Lista paginada. Devolve (itens, total), igual a patient_service.listar.

    O total é contado antes do recorte: a tela precisa dele para montar o
    paginador, e contar sobre a query já filtrada evita que o número inclua
    serviço inativo quando a listagem não os mostra.
    """
    stmt = select(Service)
    if not incluir_inativos:
        stmt = stmt.where(Service.ativo.is_(True))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    itens = (
        db.execute(stmt.order_by(Service.nome).offset((pagina - 1) * tamanho).limit(tamanho))
        .scalars()
        .all()
    )
    return list(itens), total


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
