from datetime import time
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Integer, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, coluna_enum


class JanelaReposicao(StrEnum):
    """Até quando uma falta pode ser reposta.

    Decisão OPERACIONAL, separada do ciclo de cobrança (que é financeiro).
    """

    #: Até o fim do mês do calendário em que a falta ocorreu. Padrão.
    MES_CALENDARIO = "mes_calendario"
    #: Até o fim do ciclo de cobrança do próprio paciente. Só se a cliente
    #: confirmar que pensa a reposição atrelada ao vencimento dele.
    CICLO_DO_PACIENTE = "ciclo_do_paciente"
    #: Sem prazo — repõe quando houver vaga.
    SEM_PRAZO = "sem_prazo"


class Configuracao(Base, TimestampMixin):
    """Regras de negócio que a cliente pode mudar sem deploy. Linha única.

    Nenhum destes valores existe como constante em código. Não há tela de
    configuração nesta entrega: os valores vêm do seed e se mudam por comando
    ou SQL (ver CLAUDE.md).
    """

    __tablename__ = "configuracao"
    __table_args__ = (CheckConstraint("id = 1", name="linha_unica"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # NÃO existe prazo de cancelamento. A regra das 24h foi uma premissa do
    # time, descartada: a cliente nunca falou em antecedência. O critério dela
    # é JUSTIFICATIVA, e quem classifica é a recepção. Ver premissas.md (P4).
    #
    # Confirmado pela cliente (P5): só falta justificada dá direito a repor.
    reposicao_exige_justificativa: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # JANELA DE REPOSIÇÃO — operacional, e INDEPENDENTE do ciclo de cobrança.
    #
    # Os dois só se parecem por usarem a palavra "mês". O ciclo de cobrança
    # define competência e vencimento (financeiro, Fase 5); a janela de
    # reposição define quanto tempo o paciente tem para remarcar a aula
    # perdida. Acoplar os dois foi considerado e DESCARTADO — ver
    # docs/premissas.md (P2 e P5).
    #
    # Padrão MES_CALENDARIO: quem diz "dentro do mesmo mês" quase sempre quer
    # dizer mês do calendário. Trocar é editar este registro, sem migration.
    janela_reposicao: Mapped[JanelaReposicao] = mapped_column(
        coluna_enum(JanelaReposicao),
        default=JanelaReposicao.MES_CALENDARIO,
        nullable=False,
    )
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
