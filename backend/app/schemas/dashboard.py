from pydantic import BaseModel

from app.models.booking import StatusReserva


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
