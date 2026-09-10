import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  Cobranca,
  FormaPagamento,
  Pacote,
  PaginaDeCobrancas,
  SugestaoDePacote,
  TotaisFinanceiros,
} from '@/types/financeiro'

export function useCobrancas(params: {
  filtro?: string | null
  busca?: string
  pagina?: number
}) {
  return useQuery({
    queryKey: ['cobrancas', params],
    queryFn: async (): Promise<PaginaDeCobrancas> => {
      const { data } = await api.get<PaginaDeCobrancas>('/charges', {
        params: {
          filtro: params.filtro ?? undefined,
          busca: params.busca || undefined,
          pagina: params.pagina ?? 1,
          tamanho: 30,
        },
      })
      return data
    },
    placeholderData: (anterior) => anterior,
  })
}

export function useTotais() {
  return useQuery({
    queryKey: ['cobrancas', 'totais'],
    queryFn: async (): Promise<TotaisFinanceiros> => {
      const { data } = await api.get<TotaisFinanceiros>('/charges/totais')
      return data
    },
  })
}

function useAcaoFinanceira<TVars, TResult>(fn: (v: TVars) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    // Invalida a lista E os totais: dar baixa muda os três cards do topo.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cobrancas'] }),
  })
}

export function useMarcarPago() {
  return useAcaoFinanceira(
    async (v: { id: number; forma: FormaPagamento }) =>
      (await api.post<Cobranca>(`/charges/${v.id}/pagar`, { forma_pagamento: v.forma }))
        .data,
  )
}

export function useDesfazerPagamento() {
  return useAcaoFinanceira(
    async (id: number) => (await api.post<Cobranca>(`/charges/${id}/desfazer`)).data,
  )
}

export function useCancelarCobranca() {
  return useAcaoFinanceira(
    async (v: { id: number; motivo: string }) =>
      (await api.delete<Cobranca>(`/charges/${v.id}`, { data: { motivo: v.motivo } })).data,
  )
}

export function useGerarMensalidades() {
  return useAcaoFinanceira(
    async () =>
      (
        await api.post<{ criadas: number; ja_existentes: number; matriculas: number }>(
          '/charges/gerar-mensalidades',
        )
      ).data,
  )
}

export function usePacotes(patientId?: number) {
  return useQuery({
    queryKey: ['pacotes', patientId ?? null],
    queryFn: async (): Promise<Pacote[]> => {
      const { data } = await api.get<Pacote[]>('/packages', {
        params: { patient_id: patientId },
      })
      return data
    },
  })
}

/** Valores para pré-preencher a venda. Nunca fonte de verdade. */
export function useSugestaoDePacote(serviceId: number | null) {
  return useQuery({
    queryKey: ['pacotes', 'sugestao', serviceId],
    enabled: serviceId !== null,
    queryFn: async (): Promise<SugestaoDePacote> => {
      const { data } = await api.get<SugestaoDePacote>(`/packages/sugestao/${serviceId}`)
      return data
    },
  })
}

export function useVenderPacote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (v: {
      patient_id: number
      service_id: number
      sessoes_contratadas: number
      valor_centavos: number
      validade_ate: string | null
    }) => (await api.post<Pacote>('/packages', v)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pacotes'] })
      // A venda emite cobrança no mesmo ato.
      qc.invalidateQueries({ queryKey: ['cobrancas'] })
    },
  })
}
