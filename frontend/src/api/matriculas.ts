import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { FaltaPendente, Matricula, ResultadoGeracao } from '@/types/matricula'

export function useMatriculas(patientId?: number) {
  return useQuery({
    queryKey: ['matriculas', patientId ?? null],
    queryFn: async (): Promise<Matricula[]> => {
      const { data } = await api.get<Matricula[]>('/enrollments', {
        params: { patient_id: patientId },
      })
      return data
    },
  })
}

function useAcao<TVars, TResult>(fn: (v: TVars) => Promise<TResult>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      // A grade e as reposições dependem das matrículas.
      qc.invalidateQueries({ queryKey: ['matriculas'] })
      qc.invalidateQueries({ queryKey: ['agenda'] })
      qc.invalidateQueries({ queryKey: ['reposicoes'] })
    },
  })
}

export function useCriarMatricula() {
  return useAcao(
    async (v: {
      patient_id: number
      service_id: number
      professional_id: number
      vigencia_inicio: string
      valor_mensal_centavos: number
      horarios: { dia_semana: number; hora_inicio: string }[]
    }) => (await api.post<Matricula>('/enrollments', v)).data,
  )
}

export function useSuspenderMatricula() {
  return useAcao(
    async (v: { id: number; motivo?: string }) =>
      (await api.post(`/enrollments/${v.id}/suspender`, { motivo: v.motivo })).data,
  )
}

export function useEncerrarMatricula() {
  return useAcao(
    async (v: { id: number; motivo?: string }) =>
      (await api.post(`/enrollments/${v.id}/encerrar`, { motivo: v.motivo })).data,
  )
}

export function useReativarMatricula() {
  return useAcao(
    async (id: number) => (await api.post(`/enrollments/${id}/reativar`)).data,
  )
}

export function useGerarGrade() {
  return useAcao(
    async (): Promise<ResultadoGeracao> =>
      (await api.post<ResultadoGeracao>('/enrollments/gerar-grade')).data,
  )
}

/**
 * Faltas que ainda dão direito a repor.
 *
 * É o que hoje vive na cabeça da proprietária. Cada item já traz a janela
 * (`procurar_de`/`procurar_ate`) em que a recepção deve buscar vaga.
 */
export function useReposicoesPendentes(incluirVencidas = false) {
  return useQuery({
    queryKey: ['reposicoes', incluirVencidas],
    queryFn: async (): Promise<FaltaPendente[]> => {
      const { data } = await api.get<FaltaPendente[]>('/reposicoes-pendentes', {
        params: { incluir_vencidas: incluirVencidas },
      })
      return data
    },
  })
}
