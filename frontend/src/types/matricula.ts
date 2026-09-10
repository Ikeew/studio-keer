export const STATUS_MATRICULA = ['ativa', 'suspensa', 'encerrada'] as const
export type StatusMatricula = (typeof STATUS_MATRICULA)[number]

export const STATUS_MATRICULA_LABEL: Record<StatusMatricula, string> = {
  ativa: 'Ativa',
  suspensa: 'Suspensa',
  encerrada: 'Encerrada',
}

export type HorarioFixo = {
  /** 0 = domingo … 6 = sábado */
  dia_semana: number
  hora_inicio: string
}

export type Matricula = {
  id: number
  patient_id: number
  paciente_nome: string
  service_id: number
  servico_nome: string
  professional_id: number
  instrutor_nome: string
  status: StatusMatricula
  vigencia_inicio: string
  vigencia_fim: string | null
  valor_mensal_centavos: number
  dia_vencimento: number
  horarios: HorarioFixo[]
  /** Derivada da contagem de horários — nunca um campo gravado. */
  frequencia_semanal: number
}

export type ResultadoGeracao = {
  sessoes_criadas: number
  sessoes_reaproveitadas: number
  reservas_criadas: number
  reservas_ja_existentes: number
  dias_em_blackout: number
  sem_vaga: string[]
}

/** Uma falta que ainda dá direito a repor e ainda não foi reposta. */
export type FaltaPendente = {
  booking_id: number
  patient_id: number
  paciente_nome: string
  paciente_telefone: string | null
  servico_nome: string
  service_id: number
  faltou_em: string
  justificada: boolean
  motivo: string | null
  repor_ate: string | null
  dias_restantes: number | null
  /** Janela em que faz sentido procurar vaga para esta falta. */
  procurar_de: string
  procurar_ate: string
}
