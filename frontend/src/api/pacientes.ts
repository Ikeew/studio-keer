import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type { PaginaDePacientes, Paciente } from '@/types/paciente'

export type FiltroPacientes = {
  busca?: string
  pagina?: number
  tamanho?: number
  incluirInativos?: boolean
}

const chave = {
  lista: (f: FiltroPacientes) => ['pacientes', f] as const,
}

export function usePacientes(filtro: FiltroPacientes) {
  return useQuery({
    queryKey: chave.lista(filtro),
    queryFn: async (): Promise<PaginaDePacientes> => {
      const { data } = await api.get<PaginaDePacientes>('/patients', {
        params: {
          busca: filtro.busca || undefined,
          pagina: filtro.pagina ?? 1,
          tamanho: filtro.tamanho ?? 12,
          incluir_inativos: filtro.incluirInativos ?? false,
        },
      })
      return data
    },
    // Mantém a página anterior visível enquanto a nova carrega, para a lista
    // não piscar a cada tecla digitada na busca.
    placeholderData: (anterior) => anterior,
  })
}

export type PacienteInput = {
  nome_completo: string
  cpf?: string | null
  data_nascimento?: string | null
  sexo?: string
  estado_civil?: string
  profissao?: string | null
  email?: string | null
  telefone?: string | null
  emergencia_nome?: string | null
  emergencia_telefone?: string | null
  observacoes?: string | null
  consentimento_lgpd?: boolean
}

export function useCriarPaciente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (dados: PacienteInput): Promise<Paciente> => {
      const { data } = await api.post<Paciente>('/patients', dados)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pacientes'] }),
  })
}

export function useAtualizarPaciente(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (dados: Partial<PacienteInput>): Promise<Paciente> => {
      const { data } = await api.patch<Paciente>(`/patients/${id}`, dados)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pacientes'] }),
  })
}

export function useDesativarPaciente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number): Promise<Paciente> => {
      const { data } = await api.delete<Paciente>(`/patients/${id}`)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pacientes'] }),
  })
}
