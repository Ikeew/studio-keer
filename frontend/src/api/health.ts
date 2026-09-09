import { useQuery } from '@tanstack/react-query'

import { api } from './client'

export type Health = {
  status: 'ok'
  database: 'ok' | 'unreachable'
}

/**
 * Verifica a conectividade com a API. Existe na Fase 0 para provar que o
 * caminho frontend → backend → Postgres está fechado ponta a ponta.
 */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async (): Promise<Health> => {
      const { data } = await api.get<Health>('/health')
      return data
    },
    refetchInterval: 15_000,
  })
}
