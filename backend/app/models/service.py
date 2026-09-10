from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ModeloCobranca(StrEnum):
    MENSALIDADE = "mensalidade"
    PACOTE = "pacote"


class Service(Base, TimestampMixin):
    """Serviço oferecido pelo studio.

    Os campos `sugestao_pacote_*` **nunca são fonte de verdade**. Servem só
    para pré-preencher o formulário de venda de pacote; os valores que valem
    são os capturados em `packages` no ato da venda. Ver CLAUDE.md.
    """

    __tablename__ = "services"
    __table_args__ = (
        # Sugestão de pacote em serviço de mensalidade não significa nada.
        # Validado no banco, não só na tela — esconder campo não é validação.
        CheckConstraint(
            "modelo_cobranca = 'pacote' OR ("
            " sugestao_pacote_sessoes IS NULL"
            " AND sugestao_pacote_validade_dias IS NULL"
            " AND sugestao_pacote_valor_centavos IS NULL)",
            name="sugestao_pacote_so_em_servico_de_pacote",
        ),
        CheckConstraint("capacidade_padrao > 0", name="capacidade_positiva"),
        CheckConstraint("duracao_min > 0", name="duracao_positiva"),
        CheckConstraint("preco_centavos >= 0", name="preco_nao_negativo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    duracao_min: Mapped[int] = mapped_column(Integer, nullable=False)
    # Dinheiro sempre em centavos, inteiro. Float erra o arredondamento e o
    # financeiro é a parte que a proprietária confere.
    preco_centavos: Mapped[int] = mapped_column(Integer, nullable=False)
    capacidade_padrao: Mapped[int] = mapped_column(Integer, nullable=False)
    cor: Mapped[str] = mapped_column(String(7), nullable=False)  # hex da legenda
    modelo_cobranca: Mapped[ModeloCobranca] = mapped_column(String(16), nullable=False)

    sugestao_pacote_sessoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sugestao_pacote_validade_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sugestao_pacote_valor_centavos: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Service {self.id} {self.nome}>"
