from enum import StrEnum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Papel(StrEnum):
    """Perfis de acesso do sistema.

    O studio é de uso interno: o paciente nunca entra. Nesta entrega o
    instrutor é SOMENTE LEITURA — quem registra presença e falta é a
    recepção. Ver CLAUDE.md.
    """

    ADMIN = "admin"
    RECEPCAO = "recepcao"
    INSTRUTOR = "instrutor"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    papel: Mapped[Papel] = mapped_column(
        Enum(Papel, name="papel_usuario", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Exclusão lógica: desligar alguém não pode apagar o rastro de quem
    # registrou cada agendamento e cada pagamento.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.papel.value})>"
