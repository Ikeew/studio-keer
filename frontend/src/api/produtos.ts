import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { Cobranca } from '@/types/financeiro'
import type { Produto, VendaDeProdutoInput } from '@/types/produto'

export function useProdutos() {
  return useQuery({
    queryKey: ['produtos'],
    queryFn: async (): Promise<Produto[]> => (await api.get<Produto[]>('/produtos')).data,
  })
}

/** Toda ação de estoque muda a lista de produtos; venda muda também o financeiro. */
function useAcaoDeEstoque<TVars, TResult>(fn: (v: TVars) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSettled: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ['produtos'] }),
        qc.invalidateQueries({ queryKey: ['cobrancas'] }),
        qc.invalidateQueries({ queryKey: ['dashboard'] }),
      ]),
  })
}

export function useCriarProduto() {
  return useAcaoDeEstoque(
    async (v: { nome: string; tamanho: string; preco_centavos: number; estoque_minimo: number }) =>
      (await api.post<Produto>('/produtos', v)).data,
  )
}

export function useEntradaDeEstoque() {
  return useAcaoDeEstoque(
    async (v: { id: number; quantidade: number; observacao?: string }) =>
      (
        await api.post<Produto>(`/produtos/${v.id}/entradas`, {
          quantidade: v.quantidade,
          observacao: v.observacao || null,
        })
      ).data,
  )
}

export function useVenderProduto() {
  return useAcaoDeEstoque(
    async ({ id, ...corpo }: VendaDeProdutoInput) =>
      (await api.post<Cobranca>(`/produtos/${id}/vendas`, corpo)).data,
  )
}
