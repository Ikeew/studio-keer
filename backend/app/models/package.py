from datetime import date
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class StatusPacote(StrEnum):
    ATIVO = "ativo"
    ENCERRADO = "encerrado"
    CANCELADO = "cancelado"


class Package(Base, TimestampMixin):
    """Pacote de sessões VENDIDO a um paciente.

    Cada linha é uma venda negociada caso a caso pela doutora, conforme a
    necessidade clínica. Todos os valores são SNAPSHOT do momento da venda:
    depois de vendido, o pacote nunca relê preço nem quantidade do serviço.
    Reajustar a sugestão do serviço amanhã não pode alterar o que já foi
    combinado com o paciente.

    **Não há coluna de saldo.** Saldo é derivado — ver
    `app/services/package_service.py`. Só reserva com status `presente`
    consome sessão.

    A entidade é modelada agora para a Fase 3 saber que existe; a tela de
    venda pertence ao Financeiro (Fase 5).
    """

    __tablename__ = "packages"
    __table_args__ = (
        CheckConstraint("sessoes_contratadas > 0", name="sessoes_positivas"),
        CheckConstraint("valor_centavos >= 0", name="valor_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)

    sessoes_contratadas: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nulo é caso normal, não dado faltando: significa "vale até acabar o
    # saldo". Como falta não consome sessão, a validade é a única trava do
    # pacote — ver docs/modelo-de-dados.md.
    validade_ate: Mapped[date | None] = mapped_column(Date, nullable=True)

    comprado_em: Mapped[date] = mapped_column(Date, nullable=False)
    registrado_por_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[StatusPacote] = mapped_column(
        coluna_enum(StatusPacote), default=StatusPacote.ATIVO, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Package {self.id} paciente={self.patient_id} {self.sessoes_contratadas}x>"
