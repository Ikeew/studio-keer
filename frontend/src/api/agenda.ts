import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { GradeSemanal, Origem, SessaoNaGrade } from '@/types/agenda'

export function useGradeSemanal(referencia: string) {
  return useQuery({
    queryKey: ['agenda', 'semana', referencia],
    queryFn: async (): Promise<GradeSemanal> => {
      const { data } = await api.get<GradeSemanal>('/agenda/semana', {
        params: { referencia },
      })
      return data
    },
    placeholderData: (anterior) => anterior,
  })
}

/**
 * Turmas com vaga no período.
 *
 * É o que a recepção consulta ANTES de oferecer uma reposição. Lista vazia
 * significa "não há vaga" — e a tela precisa dizer isso, não oferecer saída.
 */
export function useSessoesComVaga(params: {
  de: string
  ate: string
  serviceId?: number
  excluirPacienteId?: number
  habilitado?: boolean
}) {
  return useQuery({
    queryKey: ['agenda', 'vagas', params],
    enabled: params.habilitado ?? true,
    queryFn: async (): Promise<SessaoNaGrade[]> => {
      const { data } = await api.get<SessaoNaGrade[]>('/agenda/vagas', {
        params: {
          de: params.de,
          ate: params.ate,
          service_id: params.serviceId,
          excluir_patient_id: params.excluirPacienteId,
        },
      })
      return data
    },
  })
}

function useAcaoNaAgenda<TVars>(fn: (v: TVars) => Promise<unknown>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agenda'] }),
  })
}

export function useCriarSessao() {
  return useAcaoNaAgenda(
    async (v: {
      service_id: number
      professional_id: number
      inicia_em: string
      capacidade?: number | null
    }) => (await api.post('/sessions', v)).data,
  )
}

export function useCriarReserva() {
  return useAcaoNaAgenda(
    async (v: { session_id: number; patient_id: number; origem?: Origem }) =>
      (await api.post('/bookings', v)).data,
  )
}

export function useCancelarReserva() {
  return useAcaoNaAgenda(
    async (v: { id: number; motivo?: string }) =>
      (await api.post(`/bookings/${v.id}/cancelar`, { motivo: v.motivo })).data,
  )
}

export function useConfirmarReserva() {
  return useAcaoNaAgenda(async (id: number) => (await api.post(`/bookings/${id}/confirmar`)).data)
}

export function usePresenca() {
  return useAcaoNaAgenda(async (id: number) => (await api.post(`/bookings/${id}/presenca`)).data)
}

export function useFalta() {
  return useAcaoNaAgenda(
    async (v: { id: number; justificada: boolean; motivo?: string }) =>
      (await api.post(`/bookings/${v.id}/falta`, {
        justificada: v.justificada,
        motivo: v.motivo,
      })).data,
  )
}

export function useRemarcar() {
  return useAcaoNaAgenda(
    async (v: { id: number; nova_session_id: number; origem?: Origem }) =>
      (await api.post(`/bookings/${v.id}/remarcar`, {
        nova_session_id: v.nova_session_id,
        origem: v.origem ?? 'remarcacao',
      })).data,
  )
}

export function useCancelarSessao() {
  return useAcaoNaAgenda(
    async (v: { id: number; motivo?: string }) =>
      (await api.delete(`/sessions/${v.id}`, { data: { motivo: v.motivo } })).data,
  )
}
