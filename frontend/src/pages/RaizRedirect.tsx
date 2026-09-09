import { Navigate } from 'react-router-dom'

import { rotaInicial } from '@/auth/permissoes'
import { useAuth } from '@/auth/useAuth'

/** Manda cada perfil para a primeira tela que ele pode ver. */
export function RaizRedirect() {
  const { usuario } = useAuth()
  if (!usuario) return <Navigate to="/login" replace />
  return <Navigate to={rotaInicial(usuario.papel)} replace />
}
