import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { podeAcessar, rotaInicial } from '@/auth/permissoes'
import { useAuth } from '@/auth/useAuth'

/** Exige sessão válida e permissão de papel para a rota atual. */
export function RequireAuth() {
  const { usuario, carregando } = useAuth()
  const location = useLocation()

  // Enquanto /auth/me não responde não dá para decidir. Redirecionar aqui
  // jogaria para o login todo mundo que apenas recarregou a página.
  if (carregando) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        Carregando…
      </div>
    )
  }

  if (!usuario) {
    // Guarda o destino para voltar depois do login.
    return <Navigate to="/login" replace state={{ de: location.pathname }} />
  }

  if (!podeAcessar(usuario.papel, location.pathname)) {
    return <Navigate to={rotaInicial(usuario.papel)} replace />
  }

  return <Outlet />
}
