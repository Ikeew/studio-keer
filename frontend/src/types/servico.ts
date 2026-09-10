export const MODELOS_COBRANCA = ['mensalidade', 'pacote'] as const
export type ModeloCobranca = (typeof MODELOS_COBRANCA)[number]

export const MODELO_COBRANCA_LABEL: Record<ModeloCobranca, string> = {
  mensalidade: 'Mensalidade',
  pacote: 'Pacote de sessões',
}

export type Servico = {
  id: number
  nome: string
  duracao_min: number
  preco_centavos: number
  capacidade_padrao: number
  cor: string
  modelo_cobranca: ModeloCobranca
  /**
   * Sugestões para pré-preencher a venda de pacote. NUNCA são fonte de
   * verdade: o que vale é o negociado no ato da venda, gravado em `packages`.
   */
  sugestao_pacote_sessoes: number | null
  sugestao_pacote_validade_dias: number | null
  sugestao_pacote_valor_centavos: number | null
  ativo: boolean
}
