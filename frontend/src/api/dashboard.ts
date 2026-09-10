import { useQuery } from '@tanstack/react-query'

import { api } from './client'
import type {
  EstatisticaDeServico,
  Indicadores,
  ProximoAgendamento,
} from '@/types/dashboard'

export function useIndicadores() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: async (): Promise<Indicadores> => {
      const { data } = await api.get<Indicadores>('/dashboard')
      return data
    },
  })
}

/**
 * Aulas de hoje do instrutor autenticado.
 *
 * Não recebe id: a rota filtra pelo usuário do token, então não há como
 * pedir a agenda de outra pessoa.
 */
export function useMinhaAgenda(habilitado = true) {
  return useQuery({
    queryKey: ['minha-agenda'],
    enabled: habilitado,
    queryFn: async (): Promise<ProximoAgendamento[]> => {
      const { data } = await api.get<ProximoAgendamento[]>('/dashboard/minha-agenda')
      return data
    },
  })
}

export function useEstatisticasDeServicos() {
  return useQuery({
    queryKey: ['dashboard', 'servicos'],
    queryFn: async (): Promise<EstatisticaDeServico[]> => {
      const { data } = await api.get<EstatisticaDeServico[]>('/dashboard/servicos')
      return data
    },
  })
}
