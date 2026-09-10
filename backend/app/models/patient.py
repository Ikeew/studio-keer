from datetime import date
from enum import StrEnum

from sqlalchemy import Boolean, Date, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class Sexo(StrEnum):
    FEMININO = "feminino"
    MASCULINO = "masculino"
    OUTRO = "outro"
    NAO_INFORMADO = "nao_informado"


class EstadoCivil(StrEnum):
    SOLTEIRO = "solteiro"
    CASADO = "casado"
    DIVORCIADO = "divorciado"
    VIUVO = "viuvo"
    UNIAO_ESTAVEL = "uniao_estavel"
    NAO_INFORMADO = "nao_informado"


class Patient(Base, TimestampMixin):
    """Paciente do studio.

    NÃO guarda dado clínico: nada de queixa, lesão, restrição ou observação
    médica. Isso é dado sensível sob a LGPD (art. 5º, II) e está fora do
    escopo — adicionar "só um campinho" aqui mudaria a classificação de risco
    da tabela inteira. Ver CLAUDE.md.
    """

    __tablename__ = "patients"
    __table_args__ = (
        # Declarados aqui, e não só na migration, porque o autogenerate compara
        # o banco com Base.metadata: índice que existe no banco mas não no
        # model é interpretado como sobra e o Alembic gera um DROP para ele na
        # PRÓXIMA migration — silenciosamente.
        #
        # CPF é opcional, então a unicidade é PARCIAL: "sem CPF" nunca colide
        # com "sem CPF".
        Index(
            "ix_patients_cpf_unico",
            "cpf",
            unique=True,
            postgresql_where=text("cpf IS NOT NULL"),
        ),
        # Busca por nome sem diferenciar maiúsculas nem acento de posição.
        # Sem o trigram, o ILIKE '%termo%' varre a tabela inteira.
        Index(
            "ix_patients_nome_trgm",
            text("lower(nome_completo) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    nome_completo: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    # Opcional porque a recepção nem sempre tem o CPF na hora do cadastro.
    # Único quando informado — daí o índice único parcial na migration.
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    sexo: Mapped[Sexo] = mapped_column(
        coluna_enum(Sexo), default=Sexo.NAO_INFORMADO, nullable=False
    )
    estado_civil: Mapped[EstadoCivil] = mapped_column(
        coluna_enum(EstadoCivil), default=EstadoCivil.NAO_INFORMADO, nullable=False
    )
    profissao: Mapped[str | None] = mapped_column(String(120), nullable=True)

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    # Contato de emergência — a cliente já coleta hoje (premissas.md, P9).
    emergencia_nome: Mapped[str | None] = mapped_column(String(160), nullable=True)
    emergencia_telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LGPD: consentimento para tratamento dos dados pessoais. A data registra
    # QUANDO foi dado — sem ela o consentimento não é comprovável.
    consentimento_lgpd: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consentimento_em: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Exclusão lógica: apagar um paciente apagaria o histórico de agendamentos
    # e pagamentos junto.
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Patient {self.id} {self.nome_completo}>"
