from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class StatusSessao(StrEnum):
    AGENDADA = "agendada"
    REALIZADA = "realizada"
    CANCELADA = "cancelada"


class Session(Base, TimestampMixin):
    """Uma ocorrência concreta: este serviço, com este instrutor, neste horário.

    Sessão e reserva são coisas distintas. A sessão é a turma; quem está nela
    são os `bookings`. Ver CLAUDE.md.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("termina_em > inicia_em", name="intervalo_coerente"),
        CheckConstraint("capacidade > 0", name="capacidade_positiva"),
        Index("ix_sessions_inicia_em", "inicia_em"),
        Index("ix_sessions_profissional", "professional_id", "inicia_em"),
        # Um instrutor não pode começar duas turmas no mesmo instante.
        # LIMITAÇÃO CONHECIDA: pega início idêntico, não sobreposição parcial
        # (07:00-08:00 vs 07:30-08:30). Como toda sessão hoje começa em hora
        # cheia, cobre o caso real; sobreposição de verdade exige EXCLUDE com
        # btree_gist, avaliado e adiado em docs/modelo-de-dados.md.
        Index(
            "ix_sessions_instrutor_sem_conflito",
            "professional_id",
            "inicia_em",
            unique=True,
            postgresql_where=text("status <> 'cancelada'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    # NOT NULL de propósito: sem instrutor, o perfil de instrutor não tem o
    # que ler e a agenda não sabe de quem é a turma.
    professional_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    inicia_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    termina_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Cópia da capacidade do serviço, não join. Mudar o padrão do serviço não
    # pode reconfigurar em silêncio sessões que já têm gente marcada.
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[StatusSessao] = mapped_column(
        coluna_enum(StatusSessao), default=StatusSessao.AGENDADA, nullable=False
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Session {self.id} {self.inicia_em:%d/%m %H:%M} cap={self.capacidade}>"
