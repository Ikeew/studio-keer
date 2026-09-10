export const ORIGENS = ['recorrente', 'avulsa', 'reposicao', 'remarcacao'] as const
export type Origem = (typeof ORIGENS)[number]

export const STATUS_RESERVA = [
  'agendada',
  'confirmada',
  'presente',
  'falta',
  'cancelada',
] as const
export type StatusReserva = (typeof STATUS_RESERVA)[number]

export const STATUS_LABEL: Record<StatusReserva, string> = {
  agendada: 'Agendada',
  confirmada: 'Confirmada',
  presente: 'Presente',
  falta: 'Faltou',
  cancelada: 'Cancelada',
}

export const ORIGEM_LABEL: Record<Origem, string> = {
  recorrente: 'Horário fixo',
  avulsa: 'Avulsa',
  reposicao: 'Reposição',
  remarcacao: 'Remarcação',
}

export type ReservaNaGrade = {
  id: number
  patient_id: number
  paciente_nome: string
  posicao: number
  status: StatusReserva
  origem: Origem
  justificada: boolean
}

export type SessaoNaGrade = {
  id: number
  service_id: number
  servico_nome: string
  servico_cor: string
  professional_id: number
  instrutor_nome: string
  inicia_em: string
  termina_em: string
  hora: string
  dia: string
  capacidade: number
  ocupadas: number
  vagas: number
  lotada: boolean
  status: string
  reservas: ReservaNaGrade[]
}

export type DiaDaGrade = {
  data: string
  dia_semana: number
  aberto: boolean
  /** Já sem a pausa e sem o que está fora da janela — vem pronto da API. */
  horas: string[]
  hora_abertura: string | null
  hora_fechamento: string | null
  pausa_inicio: string | null
  pausa_fim: string | null
}

export type GradeSemanal = {
  inicio: string
  fim: string
  dias: DiaDaGrade[]
  sessoes: SessaoNaGrade[]
}

export const DIA_LABEL = [
  'Domingo',
  'Segunda',
  'Terça',
  'Quarta',
  'Quinta',
  'Sexta',
  'Sábado',
] as const
