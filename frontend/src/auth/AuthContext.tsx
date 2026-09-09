import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { api, registrarHandlerDeSessaoExpirada } from '@/api/client'
import { tokenStorage } from '@/auth/storage'
import type { LoginResponse, Usuario } from '@/types/auth'

type AuthContextValue = {
  usuario: Usuario | null
  carregando: boolean
  entrar: (email: string, senha: string) => Promise<void>
  sair: () => void
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider() {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  // Começa carregando: existe um token guardado que ainda precisa ser
  // validado contra a API antes de sabermos se a sessão vale.
  const [carregando, setCarregando] = useState(true)
  const queryClient = useQueryClient()

  const sair = useCallback(() => {
    tokenStorage.limpar()
    setUsuario(null)
    // Sem isso, o próximo usuário a entrar nesta aba veria por um instante os
    // dados em cache do anterior.
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    registrarHandlerDeSessaoExpirada(sair)
  }, [sair])

  // Restaura a sessão no boot. O token guardado pode ter expirado ou o
  // usuário pode ter sido desativado, então quem decide é a API.
  useEffect(() => {
    if (!tokenStorage.ler()) {
      setCarregando(false)
      return
    }
    api
      .get<Usuario>('/auth/me')
      .then((r) => setUsuario(r.data))
      .catch(() => tokenStorage.limpar())
      .finally(() => setCarregando(false))
  }, [])

  const entrar = useCallback(async (email: string, senha: string) => {
    // A API usa OAuth2PasswordRequestForm: form-urlencoded, campo `username`.
    const corpo = new URLSearchParams({ username: email, password: senha })
    const { data } = await api.post<LoginResponse>('/auth/login', corpo, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    tokenStorage.gravar(data.access_token)
    setUsuario(data.usuario)
  }, [])

  const value = useMemo(
    () => ({ usuario, carregando, entrar, sair }),
    [usuario, carregando, entrar, sair],
  )

  return (
    <AuthContext.Provider value={value}>
      <Outlet />
    </AuthContext.Provider>
  )
}
