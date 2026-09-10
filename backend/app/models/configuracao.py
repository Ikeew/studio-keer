from datetime import time

from sqlalchemy import Boolean, CheckConstraint, Integer, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Configuracao(Base, TimestampMixin):
    """Regras de negócio que a cliente pode mudar sem deploy. Linha única.

    Nenhum destes valores existe como constante em código. Não há tela de
    configuração nesta entrega: os valores vêm do seed e se mudam por comando
    ou SQL (ver CLAUDE.md).
    """

    __tablename__ = "configuracao"
    __table_args__ = (CheckConstraint("id = 1", name="linha_unica"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # Cancelar com esta antecedência é `cancelada`; menos que isso vira
    # `falta`. Premissa NÃO validada (premissas.md, P4).
    cancelamento_antecedencia_horas: Mapped[int] = mapped_column(
        Integer, default=24, nullable=False
    )

    # Confirmado pela cliente (P5): só falta justificada dá direito a repor.
    reposicao_exige_justificativa: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    # Premissa NÃO validada (P5).
    reposicao_prazo_mesmo_mes: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Confirmado pela cliente (P5): falta NÃO desconta do saldo do pacote.
    # É por isso que a validade vira a única trava do pacote.
    falta_consome_sessao_do_pacote: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class HorarioFuncionamento(Base, TimestampMixin):
    """Janela de atendimento, uma linha por dia da semana.

    Habilitar um dia ou mudar a janela é editar uma linha — sem migration,
    sem deploy. A pausa é por dia (e não global) para que um dia com janela
    diferente já caiba sem mudar schema.
    """

    __tablename__ = "horarios_funcionamento"
    __table_args__ = (
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="dia_semana_valido"),
        CheckConstraint("NOT aberto OR hora_fechamento > hora_abertura", name="janela_coerente"),
        CheckConstraint("(pausa_inicio IS NULL) = (pausa_fim IS NULL)", name="pausa_completa"),
    )

    # 0 = domingo … 6 = sábado (mesma convenção de date.weekday()+1 % 7 usada
    # no frontend, documentada aqui para não haver dúvida).
    dia_semana: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    aberto: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hora_abertura: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fechamento: Mapped[time] = mapped_column(Time, nullable=False)
    pausa_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    pausa_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
