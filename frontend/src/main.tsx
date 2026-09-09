import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import './index.css'
import { router } from './routes'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Não insistir em 401/403: repetir uma requisição sem permissão só
      // atrasa o redirecionamento para o login.
      retry: (falhas, erro) => {
        const status = (erro as { response?: { status?: number } })?.response?.status
        if (status === 401 || status === 403) return false
        return falhas < 1
      },
      refetchOnWindowFocus: false,
    },
  },
})

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root não encontrado no index.html')

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
