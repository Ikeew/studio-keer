from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Convenção de nomes explícita para que o Alembic gere migrations com nomes
# estáveis de constraint/índice. Sem isso, autogenerate produz nomes que o
# Postgres inventa e o downgrade fica frágil.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def coluna_enum[E: StrEnum](enum_cls: type[E]) -> Enum:
    """Tipo de coluna para um StrEnum, gravado como VARCHAR + CHECK.

    NÃO use `String(...)` com `Mapped[MeuEnum]`: a anotação mente. O valor é
    gravado certo, mas volta do banco como `str`, e toda comparação
    `x.status is MeuEnum.ALGO` passa a ser False silenciosamente. Em memória
    funciona (o objeto ainda é o original), então o bug só aparece depois de
    um reload — que é exatamente quando ninguém está olhando.

    `native_enum=False` evita criar um TYPE no Postgres. Tipo nativo obriga a
    dropar o TYPE à mão no downgrade (o autogenerate esquece) e transforma
    "adicionar um valor ao enum" numa migration com ALTER TYPE. VARCHAR com
    CHECK dá a mesma garantia com menos cerimônia, e os índices parciais que
    comparam `status <> 'cancelada'` continuam funcionando.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at/updated_at preenchidos pelo banco, não pela aplicação."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
