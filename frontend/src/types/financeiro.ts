export const STATUS_COBRANCA = ['pendente', 'pago', 'cancelado'] as const
export type StatusCobranca = (typeof STATUS_COBRANCA)[number]

export const STATUS_COBRANCA_LABEL: Record<StatusCobranca, string> = {
  pendente: 'Pendente',
  pago: 'Pago',
  cancelado: 'Cancelado',
}

export const FORMAS_PAGAMENTO = [
  'pix',
  'dinheiro',
  'debito',
  'credito',
  'transferencia',
  'outro',
] as const
export type FormaPagamento = (typeof FORMAS_PAGAMENTO)[number]

export const FORMA_LABEL: Record<FormaPagamento, string> = {
  pix: 'PIX',
  dinheiro: 'Dinheiro',
  debito: 'Débito',
  credito: 'Crédito',
  transferencia: 'Transferência',
  outro: 'Outro',
}

export type Cobranca = {
  id: number
  patient_id: number
  paciente_nome: string
  tipo: 'mensalidade' | 'pacote' | 'avulsa'
  descricao: string
  competencia_inicio: string | null
  competencia_fim: string | null
  valor_centavos: number
  vencimento: string
  status: StatusCobranca
  pago_em: string | null
  forma_pagamento: FormaPagamento | null
  /** Derivado no backend: pendente com vencimento no passado. Nunca coluna. */
  vencida: boolean
  dias_de_atraso: number
}

export type PaginaDeCobrancas = {
  itens: Cobranca[]
  total: number
  pagina: number
  tamanho: number
}

export type TotaisFinanceiros = {
  recebido_centavos: number
  pendente_centavos: number
  vencido_centavos: number
}

export type SugestaoDePacote = {
  sessoes: number | null
  validade_dias: number | null
  valor_centavos: number | null
}

export type Pacote = {
  id: number
  patient_id: number
  paciente_nome: string
  service_id: number
  servico_nome: string
  sessoes_contratadas: number
  valor_centavos: number
  validade_ate: string | null
  comprado_em: string
  status: string
  sessoes_usadas: number
  saldo: number
  /** Saldo E validade juntos — nunca só saldo. */
  utilizavel: boolean
}

export const FILTROS = [
  { valor: null, rotulo: 'Todos' },
  { valor: 'pendentes', rotulo: 'Pendentes' },
  { valor: 'pagos', rotulo: 'Pagos' },
  { valor: 'vencidos', rotulo: 'Vencidos' },
] as const
