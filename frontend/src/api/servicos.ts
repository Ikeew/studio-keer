import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { Servico } from '@/types/servico'

/** Envelope paginado devolvido por GET /services. */
type PaginaDeServicos = {
  itens: Servico[]
  total: number
  pagina: number
  tamanho: number
}

export function useServicos(incluirInativos = false) {
  return useQuery({
    queryKey: ['servicos', incluirInativos],
    // Continua entregando `Servico[]` para quem chama. O catálogo do studio
    // tem uma dúzia de itens e cabe na primeira página, então desembrulhar
    // aqui evita mexer nos quatro componentes que usam este hook só para
    // montar um select. Quando o catálogo crescer a ponto de precisar de
    // paginação na tela, o `total` já vem junto.
    queryFn: async (): Promise<Servico[]> => {
      const { data } = await api.get<PaginaDeServicos>('/services', {
        params: { incluir_inativos: incluirInativos },
      })
      return data.itens
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
