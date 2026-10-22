from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class Produto(Base, TimestampMixin):
    """Produto vendido no balcão (meia, camiseta), um por TAMANHO.

    Estoque bem simples, a pedido da equipe: sem fornecedor, lote nem nota de
    entrada. Cada tamanho é um produto próprio ("Camiseta" / "M"), porque é
    por tamanho que o estoque acaba.

    A quantidade em estoque NÃO é coluna: é a soma de `movimentos_estoque`.
    Um contador gravado sai de sincronia na primeira venda concorrente — a
    mesma regra das vagas da turma (CLAUDE.md, "o que é derivado nunca é
    armazenado").
    """

    __tablename__ = "produtos"
    __table_args__ = (
        UniqueConstraint("nome", "tamanho", name="uq_produtos_nome_tamanho"),
        CheckConstraint("preco_centavos >= 0", name="preco_nao_negativo"),
        CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Texto livre ("P", "M", "G", "Único"): os tamanhos vendidos mudam sem
    #: migration.
    tamanho: Mapped[str] = mapped_column(String(20), nullable=False)
    preco_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Abaixo ou igual a isto, a tela avisa que está acabando.
    estoque_minimo: Mapped[int] = mapped_column(Integer, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Produto {self.id} {self.nome} {self.tamanho}>"


class TipoMovimento(StrEnum):
    ENTRADA = "entrada"  # reposição manual
    VENDA = "venda"  # baixa automática na venda
    ESTORNO = "estorno"  # venda cancelada devolve ao estoque


class MovimentoEstoque(Base):
    """Uma entrada ou saída de estoque. Nunca editada: corrige-se com outra."""

    __tablename__ = "movimentos_estoque"
    __table_args__ = (
        CheckConstraint("quantidade <> 0", name="quantidade_nao_zero"),
        # O sinal acompanha o tipo: venda tira, entrada e estorno devolvem.
        CheckConstraint("(tipo = 'venda') = (quantidade < 0)", name="sinal_coerente_com_tipo"),
        CheckConstraint("tipo = 'entrada' OR charge_id IS NOT NULL", name="venda_tem_cobranca"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False, index=True)
    #: Positiva na entrada e no estorno, negativa na venda.
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[TipoMovimento] = mapped_column(coluna_enum(TipoMovimento), nullable=False)
    charge_id: Mapped[int | None] = mapped_column(ForeignKey("charges.id"), nullable=True)
    observacao: Mapped[str | None] = mapped_column(String(300), nullable=True)
    registrado_por_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MovimentoEstoque {self.produto_id} {self.tipo} {self.quantidade}>"
