import type { FormaPagamento } from '@/types/financeiro'

/** Produto de balcão, um por tamanho ("Camiseta" P, M e G são três). */
export type Produto = {
  id: number
  nome: string
  tamanho: string
  preco_centavos: number
  estoque_minimo: number
  ativo: boolean
  /** Soma dos movimentos — derivado no backend, nunca coluna. */
  estoque: number
  /** Chegou ao mínimo: alerta visual. */
  acabando: boolean
}

export type VendaDeProdutoInput = {
  id: number
  quantidade: number
  forma_pagamento: FormaPagamento
  patient_id?: number | null
  comprador_nome?: string | null
}
