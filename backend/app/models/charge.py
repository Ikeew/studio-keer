from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class TipoCobranca(StrEnum):
    MENSALIDADE = "mensalidade"
    PACOTE = "pacote"
    AVULSA = "avulsa"


class StatusCobranca(StrEnum):
    """Eixo de PAGAMENTO. Presença vive em `bookings` e nunca se mistura aqui.

    `vencido` NÃO é status: é `pendente AND vencimento < hoje`, calculado na
    consulta. Um status gravado exigiria um job à meia-noite e mentiria até
    ele rodar.
    """

    PENDENTE = "pendente"
    PAGO = "pago"
    CANCELADO = "cancelado"


class FormaPagamento(StrEnum):
    DINHEIRO = "dinheiro"
    PIX = "pix"
    DEBITO = "debito"
    CREDITO = "credito"
    TRANSFERENCIA = "transferencia"
    OUTRO = "outro"


_ATIVA = "status <> 'cancelado'"


class Charge(Base, TimestampMixin):
    """Uma cobrança: mensalidade de um ciclo, pacote vendido ou sessão avulsa."""

    __tablename__ = "charges"
    __table_args__ = (
        CheckConstraint("valor_centavos >= 0", name="valor_nao_negativo"),
        CheckConstraint("status <> 'pago' OR pago_em IS NOT NULL", name="pago_tem_data"),
        # Uma mensalidade por ciclo. É o que torna a geração IDEMPOTENTE no
        # banco: rodar duas vezes não cobra o paciente duas vezes.
        Index(
            "ix_charges_mensalidade_por_ciclo",
            "enrollment_id",
            "competencia_inicio",
            unique=True,
            postgresql_where=text(f"tipo = 'mensalidade' AND {_ATIVA}"),
        ),
        # Um pacote gera UMA cobrança, no ato da venda.
        Index(
            "ix_charges_pacote_unico",
            "package_id",
            unique=True,
            postgresql_where=text(f"tipo = 'pacote' AND {_ATIVA}"),
        ),
        Index("ix_charges_status_vencimento", "status", "vencimento"),
        Index("ix_charges_paciente", "patient_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)

    # Origem da cobrança — no máximo uma está preenchida.
    enrollment_id: Mapped[int | None] = mapped_column(ForeignKey("enrollments.id"), nullable=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id"), nullable=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)

    tipo: Mapped[TipoCobranca] = mapped_column(coluna_enum(TipoCobranca), nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)

    # O ciclo coberto, só em mensalidade. `competencia_inicio` é a identidade
    # do ciclo — ver ciclo_service.Competencia.chave.
    competencia_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    competencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Dinheiro sempre em centavos, inteiro.
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[StatusCobranca] = mapped_column(
        coluna_enum(StatusCobranca), default=StatusCobranca.PENDENTE, nullable=False
    )
    pago_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forma_pagamento: Mapped[FormaPagamento | None] = mapped_column(
        coluna_enum(FormaPagamento), nullable=True
    )

    registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(300), nullable=True)

    def __repr__(self) -> str:
        return f"<Charge {self.id} {self.tipo} {self.valor_centavos}c {self.status}>"
