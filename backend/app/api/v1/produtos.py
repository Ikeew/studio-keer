from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.api.v1.financeiro import cobranca_para_leitura
from app.core.deps import CurrentUser, require_papel
from app.db.session import get_db
from app.models.user import Papel
from app.schemas.financeiro import ChargeRead
from app.schemas.produto import (
    EntradaDeEstoque,
    ProdutoCreate,
    ProdutoRead,
    ProdutoUpdate,
    VendaDeProduto,
)
from app.services import produto_service

router = APIRouter(tags=["estoque"])

Db = Annotated[DbSession, Depends(get_db)]

# Vender e repor estoque é operação de balcão: recepção e proprietária.
OPERADORES = Depends(require_papel(Papel.ADMIN, Papel.RECEPCAO))
# Cadastro e preço são decisão da proprietária.
SO_ADMIN = Depends(require_papel(Papel.ADMIN))


def _para_leitura(item: produto_service.ProdutoComEstoque) -> ProdutoRead:
    p = item.produto
    return ProdutoRead(
        id=p.id,
        nome=p.nome,
        tamanho=p.tamanho,
        preco_centavos=p.preco_centavos,
        estoque_minimo=p.estoque_minimo,
        ativo=p.ativo,
        estoque=item.estoque,
        acabando=item.acabando,
    )


def _recarregar(db: DbSession, produto_id: int) -> ProdutoRead:
    produto = produto_service.buscar(db, produto_id)
    return _para_leitura(
        produto_service.ProdutoComEstoque(produto, produto_service.estoque(db, produto_id))
    )


@router.get("/produtos", response_model=list[ProdutoRead], dependencies=[OPERADORES])
def listar(db: Db, incluir_inativos: bool = False) -> list[ProdutoRead]:
    return [_para_leitura(i) for i in produto_service.listar(db, incluir_inativos=incluir_inativos)]


@router.post(
    "/produtos",
    response_model=ProdutoRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[SO_ADMIN],
)
def criar(dados: ProdutoCreate, db: Db) -> ProdutoRead:
    """Um produto por tamanho: "Camiseta" P, M e G são três cadastros."""
    produto = produto_service.criar(
        db,
        nome=dados.nome,
        tamanho=dados.tamanho,
        preco_centavos=dados.preco_centavos,
        estoque_minimo=dados.estoque_minimo,
    )
    db.commit()
    return _recarregar(db, produto.id)


@router.patch("/produtos/{produto_id}", response_model=ProdutoRead, dependencies=[SO_ADMIN])
def atualizar(produto_id: int, dados: ProdutoUpdate, db: Db) -> ProdutoRead:
    produto = produto_service.buscar(db, produto_id)
    for campo, valor in dados.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(produto, campo, valor)
    db.commit()
    return _recarregar(db, produto_id)


@router.post(
    "/produtos/{produto_id}/entradas", response_model=ProdutoRead, dependencies=[OPERADORES]
)
def registrar_entrada(
    produto_id: int, dados: EntradaDeEstoque, db: Db, usuario: CurrentUser
) -> ProdutoRead:
    """Chegou mercadoria. Fica registrado quem lançou."""
    produto_service.registrar_entrada(
        db,
        produto_id,
        quantidade=dados.quantidade,
        observacao=dados.observacao,
        registrado_por_id=usuario.id,
    )
    db.commit()
    return _recarregar(db, produto_id)


@router.post(
    "/produtos/{produto_id}/vendas",
    response_model=ChargeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[OPERADORES],
)
def vender(produto_id: int, dados: VendaDeProduto, db: Db, usuario: CurrentUser) -> ChargeRead:
    """Vende e dá baixa no estoque. A cobrança já nasce paga.

    409 se não houver estoque suficiente.
    """
    cobranca = produto_service.vender(
        db,
        produto_id,
        quantidade=dados.quantidade,
        forma=dados.forma_pagamento,
        registrado_por_id=usuario.id,
        patient_id=dados.patient_id,
        comprador_nome=dados.comprador_nome,
    )
    db.commit()
    return cobranca_para_leitura(db, cobranca)
