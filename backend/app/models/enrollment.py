from datetime import date, time
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, coluna_enum


class StatusMatricula(StrEnum):
    ATIVA = "ativa"
    SUSPENSA = "suspensa"
    ENCERRADA = "encerrada"


class Enrollment(Base, TimestampMixin):
    """A mensalidade: horário fixo semanal contratado por um paciente.

    Só mensalidade. Pacote de sessões é `packages`, entidade separada — ver
    docs/modelo-de-dados.md.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        CheckConstraint("valor_mensal_centavos >= 0", name="valor_nao_negativo"),
        CheckConstraint(
            "vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio",
            name="vigencia_coerente",
        ),
        Index("ix_enrollments_paciente", "patient_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    professional_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    status: Mapped[StatusMatricula] = mapped_column(
        coluna_enum(StatusMatricula), default=StatusMatricula.ATIVA, nullable=False
    )
    vigencia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Snapshot no momento da contratação. Reajustar o preço do serviço não
    # pode alterar retroativamente o que alguém já assinou.
    valor_mensal_centavos: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dia do vencimento: cada paciente vence no dia em que começou, mês cheio
    # e sem proporcional (confirmado pela cliente, premissas.md P2). O CICLO
    # de referência é decisão da Fase 5 e não afeta a agenda.
    dia_vencimento: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    horarios: Mapped[list["EnrollmentHorario"]] = relationship(
        back_populates="matricula", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Enrollment {self.id} paciente={self.patient_id} {self.status}>"


class EnrollmentHorario(Base, TimestampMixin):
    """Um horário fixo semanal da matrícula.

    2x/semana são DUAS linhas. A frequência é `COUNT(*)`, nunca um campo —
    campo poderia discordar das linhas e alguém pagaria por 3x tendo 2
    horários.
    """

    __tablename__ = "enrollment_horarios"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="dia_semana_valido"),
        # A mesma matrícula não repete o mesmo horário.
        Index(
            "ix_enrollment_horarios_unico",
            "enrollment_id",
            "dia_semana",
            "hora_inicio",
            unique=True,
        ),
        Index("ix_enrollment_horarios_slot", "dia_semana", "hora_inicio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    # 0 = domingo … 6 = sábado, mesma convenção de horarios_funcionamento.
    dia_semana: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)

    matricula: Mapped[Enrollment] = relationship(back_populates="horarios")


class Blackout(Base, TimestampMixin):
    """Feriado ou recesso: período em que o studio não atende.

    Não gera sessão. Criado DEPOIS de sessões existirem, o sistema AVISA em
    vez de apagar em silêncio — mesmo princípio da redução de capacidade.
    """

    __tablename__ = "blackouts"
    __table_args__ = (
        CheckConstraint("data_fim >= data_inicio", name="periodo_coerente"),
        Index("ix_blackouts_periodo", "data_inicio", "data_fim"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    motivo: Mapped[str] = mapped_column(String(160), nullable=False)
