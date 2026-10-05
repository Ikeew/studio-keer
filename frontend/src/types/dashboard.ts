import type { Origem, StatusReserva } from './agenda'
import type { FormaPagamento } from './financeiro'

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

// ---------------------------------------------------------------------------
// Análise do período — GET /dashboard/analise?meses=N
// Datas trafegam como "YYYY-MM-DD"; dinheiro como inteiro em centavos.
// ---------------------------------------------------------------------------

export type PeriodoDeAnalise = {
  inicio: string
  fim: string
  meses: number
  /** "semana" quando meses == 1; senão "mes". */
  granularidade: 'semana' | 'mes'
}

export type TipoDeCobranca = 'mensalidade' | 'pacote' | 'avulsa'

export type BaldeDeReceita = {
  inicio: string
  fim: string
  recebido_centavos: number
  /** As três chaves vêm sempre presentes. */
  por_tipo: Record<TipoDeCobranca, number>
  /** Só o balde que contém hoje — ainda pode crescer. */
  em_andamento: boolean
}

export type ReceitaDoPeriodo = {
  recebido_centavos: number
  pagamentos: number
  serie: BaldeDeReceita[]
}

export type UsoDeFormaDePagamento = {
  /** null = "Não informada". */
  forma: FormaPagamento | null
  pagamentos: number
  valor_centavos: number
}

export type ServicoNoPeriodo = {
  service_id: number
  nome: string
  cor: string
  sessoes: number
  reservas: number
  ocupacao_percentual: number
}

export type CelulaDeHorario = {
  /** Convenção do banco: 0 = domingo … 6 = sábado. */
  dia_semana: number
  hora: number
  sessoes: number
  reservas: number
  capacidade: number
  ocupacao_percentual: number
}

export type HorariosDoPeriodo = {
  /** Ordem segunda-primeiro (1..6, depois 0). */
  dias: number[]
  horas: number[]
  /** Só combinações que tiveram sessão. */
  celulas: CelulaDeHorario[]
  /**
   * Horas atendíveis de cada dia de `dias` pela configuração de funcionamento
   * (já sem a pausa); [] quando o dia está fechado. Separa "sem turma" (aberto,
   * ninguém comprou) de "fechado" (o studio não atende ali). No JSON a chave
   * chega como string; o acesso por número funciona igual.
   */
  horas_por_dia: Record<number, number[]>
}

export type PresencaDoPeriodo = {
  presentes: number
  faltas_justificadas: number
  faltas_nao_justificadas: number
  /** Sessão já começou e ninguém marcou presença (docs/premissas.md P8). */
  sem_registro: number
  a_realizar: number
  canceladas: number
  comparecimento_percentual: number
}

export type ReservasPorOrigem = {
  origem: Origem
  reservas: number
}

export type Analise = {
  periodo: PeriodoDeAnalise
  receita: ReceitaDoPeriodo
  formas_pagamento: UsoDeFormaDePagamento[]
  servicos: ServicoNoPeriodo[]
  ocupacao: TaxaDeOcupacao
  horarios: HorariosDoPeriodo
  presenca: PresencaDoPeriodo
  /** Sempre as quatro, na ordem do enum. */
  origens: ReservasPorOrigem[]
}
