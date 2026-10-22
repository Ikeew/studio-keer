"""Estoque simples de produtos de balcão (meia, camiseta).

A pedido da equipe, "bem simples": quantidade por produto, baixa automática
na venda, entrada manual e aviso quando está acabando. Sem fornecedor, lote
nem nota de entrada.

O estoque é SEMPRE a soma dos movimentos — nunca um contador gravado.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.models.charge import Charge, FormaPagamento, StatusCobranca, TipoCobranca
from app.models.patient import Patient
from app.models.produto import MovimentoEstoque, Produto, TipoMovimento

#: Nome da cobrança quando quem compra não é paciente e ninguém informou.
COMPRADOR_PADRAO = "Studio Keer"


@dataclass
class ProdutoComEstoque:
    produto: Produto
    estoque: int

    @property
    def acabando(self) -> bool:
        """Alerta visual: chegou ao mínimo (ou zerou)."""
        return self.estoque <= self.produto.estoque_minimo


def _estoques(db: DbSession, ids: list[int]) -> dict[int, int]:
    """Estoque de vários produtos numa consulta só."""
    if not ids:
        return {}
    linhas = db.execute(
        select(MovimentoEstoque.produto_id, func.coalesce(func.sum(MovimentoEstoque.quantidade), 0))
        .where(MovimentoEstoque.produto_id.in_(ids))
        .group_by(MovimentoEstoque.produto_id)
    ).all()
    return {pid: int(total) for pid, total in linhas}


def estoque(db: DbSession, produto_id: int) -> int:
    return _estoques(db, [produto_id]).get(produto_id, 0)


def listar(db: DbSession, *, incluir_inativos: bool = False) -> list[ProdutoComEstoque]:
    stmt = select(Produto).order_by(Produto.nome, Produto.tamanho)
    if not incluir_inativos:
        stmt = stmt.where(Produto.ativo.is_(True))
    produtos = list(db.execute(stmt).scalars())
    saldos = _estoques(db, [p.id for p in produtos])
    return [ProdutoComEstoque(p, saldos.get(p.id, 0)) for p in produtos]


def buscar(db: DbSession, produto_id: int, *, travar: bool = False) -> Produto:
    stmt = select(Produto).where(Produto.id == produto_id)
    if travar:
        stmt = stmt.with_for_update()
    produto = db.execute(stmt).scalar_one_or_none()
    if produto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado")
    return produto


def criar(
    db: DbSession, *, nome: str, tamanho: str, preco_centavos: int, estoque_minimo: int
) -> Produto:
    produto = Produto(
        nome=nome,
        tamanho=tamanho,
        preco_centavos=preco_centavos,
        estoque_minimo=estoque_minimo,
    )
    db.add(produto)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe {nome} no tamanho {tamanho}.",
        ) from exc
    return produto


def registrar_entrada(
    db: DbSession,
    produto_id: int,
    *,
    quantidade: int,
    registrado_por_id: int,
    observacao: str | None = None,
) -> MovimentoEstoque:
    """Reposição manual: chegou mercadoria."""
    buscar(db, produto_id)
    movimento = MovimentoEstoque(
        produto_id=produto_id,
        quantidade=quantidade,
        tipo=TipoMovimento.ENTRADA,
        observacao=observacao,
        registrado_por_id=registrado_por_id,
    )
    db.add(movimento)
    db.flush()
    return movimento


def vender(
    db: DbSession,
    produto_id: int,
    *,
    quantidade: int,
    forma: FormaPagamento,
    registrado_por_id: int,
    patient_id: int | None = None,
    comprador_nome: str | None = None,
) -> Charge:
    """Vende, dá baixa no estoque e lança a cobrança JÁ PAGA, num ato só.

    A venda é de balcão: o produto sai na hora e o pagamento também
    (confirmado pela equipe). A cobrança nasce paga, com a forma escolhida.

    O FOR UPDATE no produto serializa duas vendas da última peça: a segunda
    espera, relê o estoque e é recusada, em vez de deixá-lo negativo.
    """
    produto = buscar(db, produto_id, travar=True)
    if not produto.ativo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Este produto não está mais à venda."
        )

    disponivel = estoque(db, produto_id)
    if quantidade > disponivel:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Estoque insuficiente de {produto.nome} {produto.tamanho}: "
                f"{'nenhuma unidade' if disponivel == 0 else f'restam {disponivel}'}."
            ),
        )

    if patient_id is not None and db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado")

    cobranca = Charge(
        patient_id=patient_id,
        comprador_nome=None if patient_id is not None else (comprador_nome or COMPRADOR_PADRAO),
        tipo=TipoCobranca.PRODUTO,
        descricao=f"{produto.nome} {produto.tamanho} ({quantidade} un.)",
        valor_centavos=produto.preco_centavos * quantidade,
        vencimento=date.today(),
        status=StatusCobranca.PAGO,
        pago_em=datetime.now(UTC),
        forma_pagamento=forma,
        registrado_por_id=registrado_por_id,
    )
    db.add(cobranca)
    db.flush()

    db.add(
        MovimentoEstoque(
            produto_id=produto_id,
            quantidade=-quantidade,
            tipo=TipoMovimento.VENDA,
            charge_id=cobranca.id,
            registrado_por_id=registrado_por_id,
        )
    )
    db.flush()
    return cobranca


def estornar_venda(db: DbSession, cobranca: Charge, *, registrado_por_id: int) -> None:
    """Venda cancelada devolve as peças ao estoque. Uma vez só por venda."""
    venda = db.execute(
        select(MovimentoEstoque).where(
            MovimentoEstoque.charge_id == cobranca.id,
            MovimentoEstoque.tipo == TipoMovimento.VENDA,
        )
    ).scalar_one_or_none()
    if venda is None:
        return
    ja_estornada = db.execute(
        select(MovimentoEstoque.id).where(
            MovimentoEstoque.charge_id == cobranca.id,
            MovimentoEstoque.tipo == TipoMovimento.ESTORNO,
        )
    ).first()
    if ja_estornada is not None:
        return
    db.add(
        MovimentoEstoque(
            produto_id=venda.produto_id,
            quantidade=-venda.quantidade,
            tipo=TipoMovimento.ESTORNO,
            charge_id=cobranca.id,
            observacao="Venda cancelada",
            registrado_por_id=registrado_por_id,
        )
    )
    db.flush()
