from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.models.booking import OrigemReserva, StatusReserva
from app.models.charge import FormaPagamento, TipoCobranca


class TaxaDeOcupacaoRead(BaseModel):
    """Taxa de ocupação, com o numerador e o denominador expostos.

    Os dois números aparecem na resposta de propósito: um percentual sozinho
    não é auditável, e este é o indicador que a banca vai questionar.
    """

    percentual: int
    reservas_ativas: int
    capacidade_ofertada: int
    #: A fórmula em texto, para a tela poder mostrar sem duplicar a regra.
    formula: str


class ProximoAgendamentoRead(BaseModel):
    booking_id: int
    hora: str
    paciente_nome: str
    servico_nome: str
    instrutor_nome: str
    status: StatusReserva


class IndicadoresRead(BaseModel):
    agendamentos_hoje: int
    pacientes_ativos: int
    sessoes_no_mes: int
    ocupacao: TaxaDeOcupacaoRead
    proximos: list[ProximoAgendamentoRead]


class EstatisticaDeServicoRead(BaseModel):
    service_id: int
    nome: str
    cor: str
    sessoes_no_mes: int
    reservas_no_mes: int
    ocupacao_percentual: int


# ── Análise do período ──────────────────────────────────────────────────────
# As definições de cada indicador estão nos dataclasses de
# app/services/dashboard_service.py; aqui só o formato da resposta.


class PeriodoRead(BaseModel):
    inicio: date
    fim: date
    meses: int
    granularidade: Literal["semana", "mes"]


class BaldeDeReceitaRead(BaseModel):
    inicio: date
    fim: date
    recebido_centavos: int
    #: Sempre as três chaves de TipoCobranca, zero quando não houver.
    por_tipo: dict[TipoCobranca, int]
    #: True só no balde que contém hoje — ainda vai crescer.
    em_andamento: bool


class ReceitaRead(BaseModel):
    recebido_centavos: int
    pagamentos: int
    serie: list[BaldeDeReceitaRead]


class FormaDePagamentoRead(BaseModel):
    #: None = "Não informada".
    forma: FormaPagamento | None
    pagamentos: int
    valor_centavos: int


class ServicoNoPeriodoRead(BaseModel):
    service_id: int
    nome: str
    cor: str
    sessoes: int
    reservas: int
    ocupacao_percentual: int


class CelulaDeHorarioRead(BaseModel):
    #: 0 = domingo … 6 = sábado (convenção do banco).
    dia_semana: int
    hora: int
    sessoes: int
    reservas: int
    capacidade: int
    ocupacao_percentual: int


class HorariosRead(BaseModel):
    #: Segunda primeiro, domingo por último.
    dias: list[int]
    horas: list[int]
    #: Uma entrada por dia de `dias`: as horas atendíveis dele na configuração
    #: atual ([] se fechado). Sem sessão e fora desta lista é "fechado", não
    #: "sem turma" — `horas` é a união dos dias e não distingue os dois.
    horas_por_dia: dict[int, list[int]]
    #: Só as combinações que tiveram sessão.
    celulas: list[CelulaDeHorarioRead]


class PresencaRead(BaseModel):
    presentes: int
    faltas_justificadas: int
    faltas_nao_justificadas: int
    sem_registro: int
    a_realizar: int
    canceladas: int
    comparecimento_percentual: int


class OrigemRead(BaseModel):
    origem: OrigemReserva
    reservas: int


class AnaliseRead(BaseModel):
    periodo: PeriodoRead
    receita: ReceitaRead
    formas_pagamento: list[FormaDePagamentoRead]
    servicos: list[ServicoNoPeriodoRead]
    ocupacao: TaxaDeOcupacaoRead
    horarios: HorariosRead
    presenca: PresencaRead
    origens: list[OrigemRead]
