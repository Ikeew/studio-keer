import type { StatusReserva } from './agenda'

export type TaxaDeOcupacao = {
  percentual: number
  /** Numerador e denominador vêm expostos: percentual sozinho não é auditável. */
  reservas_ativas: number
  capacidade_ofertada: number
  formula: string
}

export type ProximoAgendamento = {
  booking_id: number
  hora: string
  paciente_nome: string
  servico_nome: string
  instrutor_nome: string
  status: StatusReserva
}

export type Indicadores = {
  agendamentos_hoje: number
  pacientes_ativos: number
  sessoes_no_mes: number
  ocupacao: TaxaDeOcupacao
  proximos: ProximoAgendamento[]
}

export type EstatisticaDeServico = {
  service_id: number
  nome: string
  cor: string
  sessoes_no_mes: number
  reservas_no_mes: number
  ocupacao_percentual: number
}
