import axios from 'axios'

import { tokenStorage } from '@/auth/storage'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenStorage.ler()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** Executado quando a API devolve 401. Definido pelo AuthProvider. */
let aoExpirarSessao: (() => void) | null = null

export function registrarHandlerDeSessaoExpirada(fn: () => void): void {
  aoExpirarSessao = fn
}

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error?.response?.status
    // 401 = não autenticado: token expirou ou é inválido, desloga.
    // 403 = autenticado sem permissão: NÃO desloga, senão o instrutor seria
    // expulso do sistema ao esbarrar numa tela de admin.
    if (status === 401) aoExpirarSessao?.()
    return Promise.reject(error)
  },
)
