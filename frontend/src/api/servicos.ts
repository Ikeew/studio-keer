import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { Servico } from '@/types/servico'

export function useServicos(incluirInativos = false) {
  return useQuery({
    queryKey: ['servicos', incluirInativos],
    queryFn: async (): Promise<Servico[]> => {
      const { data } = await api.get<Servico[]>('/services', {
        params: { incluir_inativos: incluirInativos },
      })
      return data
    },
  })
}

export type ServicoInput = {
  nome: string
  duracao_min: number
  preco_centavos: number
  capacidade_padrao: number
  cor: string
  modelo_cobranca: string
  sugestao_pacote_sessoes?: number | null
  sugestao_pacote_validade_dias?: number | null
  sugestao_pacote_valor_centavos?: number | null
}

export function useCriarServico() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (dados: ServicoInput): Promise<Servico> => {
      const { data } = await api.post<Servico>('/services', dados)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servicos'] }),
  })
}

export function useAtualizarServico(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (dados: ServicoInput & { ativo: boolean }): Promise<Servico> => {
      const { data } = await api.put<Servico>(`/services/${id}`, dados)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['servicos'] }),
  })
}
