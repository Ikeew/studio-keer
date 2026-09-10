import { useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { Usuario } from '@/types/auth'

/**
 * Instrutores disponíveis para ministrar uma turma.
 *
 * `/users` é restrita ao admin, então a recepção receberia 403. Como a
 * recepção precisa escolher o instrutor ao criar uma turma, este hook usa a
 * rota dedicada — que devolve só nome e id, sem e-mail nem papel.
 */
export function useInstrutores(habilitado = true) {
  return useQuery({
    queryKey: ['instrutores'],
    // O instrutor recebe 403 nesta rota. Desabilitar evita a requisição
    // inútil e o erro no console dele.
    enabled: habilitado,
    queryFn: async (): Promise<Usuario[]> => {
      const { data } = await api.get<Usuario[]>('/instrutores')
      return data
    },
  })
}
