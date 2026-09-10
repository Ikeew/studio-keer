from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class OrigemReserva(StrEnum):
    RECORRENTE = "recorrente"  # gerada pela matrícula (Fase 4)
    AVULSA = "avulsa"
    REPOSICAO = "reposicao"
    REMARCACAO = "remarcacao"


class StatusReserva(StrEnum):
    """Eixo de PRESENÇA. Pagamento vive em `charges` e nunca se mistura aqui.

    agendada → confirmada → presente | falta
    cancelada é saída em qualquer ponto antes da aula.
    """

    AGENDADA = "agendada"
    CONFIRMADA = "confirmada"
    PRESENTE = "presente"
    FALTA = "falta"
    CANCELADA = "cancelada"


#: Reservas que ocupam vaga. Cancelada NÃO ocupa — é isso que faz o
#: cancelamento devolver a vaga para uma reposição, na mesma transação.
STATUS_QUE_OCUPAM_VAGA = (
    StatusReserva.AGENDADA,
    StatusReserva.CONFIRMADA,
    StatusReserva.PRESENTE,
    StatusReserva.FALTA,
)

_SQL_OCUPA_VAGA = "status <> 'cancelada'"


class Booking(Base, TimestampMixin):
    """A reserva de um paciente numa sessão.

    ── COMO A CAPACIDADE VIRA INVIOLÁVEL ────────────────────────────────────

    Capacidade é um limite de CONTAGEM, e contagem não se expressa em índice
    único. A saída é dar a cada reserva uma POSIÇÃO na turma (1..capacidade) e
    tornar a posição única por sessão:

        UNIQUE (session_id, posicao) WHERE status <> 'cancelada'

    Com isso, duas recepcionistas disputando a última vaga calculam a mesma
    posição, e o banco reprova uma das duas — não a aplicação. Some a corrida.

    O índice sozinho, porém, garante só que ninguém repete posição; quem
    decide que a posição cabe é a aplicação. Para fechar também esse furo, a
    reserva guarda `capacidade_sessao`, cópia da capacidade no momento da
    marcação, com CHECK (posicao <= capacidade_sessao). Assim um bug de código
    que tentasse a posição 5 numa turma de 4 seria recusado pelo banco.

    A cópia não vira mentira quando a capacidade do serviço muda: reservas
    existentes mantêm sua posição (o sistema avisa, não remove — ver CLAUDE.md)
    e reservas novas passam a usar a capacidade nova.

    O índice ser PARCIAL é o que implementa "cancelar libera a vaga": ao virar
    `cancelada`, a linha sai do índice e a posição volta ao pool.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        # A trava de capacidade.
        Index(
            "ix_bookings_posicao_unica",
            "session_id",
            "posicao",
            unique=True,
            postgresql_where=text(_SQL_OCUPA_VAGA),
        ),
        # A mesma pessoa não ocupa duas vagas da mesma turma.
        Index(
            "ix_bookings_paciente_unico_na_sessao",
            "session_id",
            "patient_id",
            unique=True,
            postgresql_where=text(_SQL_OCUPA_VAGA),
        ),
        # Uma falta gera UMA reposição. Sem isto, repor duas vezes a mesma
        # falta seria overbooking por outra porta.
        Index(
            "ix_bookings_substitui_unico",
            "substitui_booking_id",
            unique=True,
            postgresql_where=text(f"substitui_booking_id IS NOT NULL AND {_SQL_OCUPA_VAGA}"),
        ),
        Index("ix_bookings_paciente", "patient_id", "status"),
        CheckConstraint("posicao >= 1", name="posicao_positiva"),
        CheckConstraint("posicao <= capacidade_sessao", name="posicao_dentro_da_capacidade"),
        CheckConstraint(
            "status <> 'cancelada' OR cancelado_em IS NOT NULL",
            name="cancelada_tem_data",
        ),
        # Uma reserva não é reposição de si mesma.
        CheckConstraint(
            "substitui_booking_id IS NULL OR substitui_booking_id <> id",
            name="nao_substitui_a_si_mesma",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    # Consome saldo de um pacote vendido. Nulo em reserva avulsa.
    # `enrollment_id` chega na Fase 4, junto com as matrículas.
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id"), nullable=True)

    posicao: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    capacidade_sessao: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    origem: Mapped[OrigemReserva] = mapped_column(coluna_enum(OrigemReserva), nullable=False)
    status: Mapped[StatusReserva] = mapped_column(
        coluna_enum(StatusReserva), default=StatusReserva.AGENDADA, nullable=False
    )

    # Julgamento HUMANO da recepção — o sistema nunca infere. Não existe prazo
    # de antecedência que classifique sozinho: a regra das 24h era premissa do
    # time e foi descartada (docs/premissas.md, P4).
    justificada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    motivo_justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vale para reposição E remarcação; `origem` diz qual das duas.
    substitui_booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.id"), nullable=True
    )

    # Informação, não regra: diz QUANDO a vaga liberou.
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text, nullable=True)

    criado_por_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    def __repr__(self) -> str:
        return f"<Booking {self.id} sessao={self.session_id} pos={self.posicao} {self.status}>"
