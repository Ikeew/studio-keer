import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthContext'
import { RequireAuth } from '@/auth/RequireAuth'
import { AppLayout } from '@/components/layout/AppLayout'
import { Agenda } from '@/pages/Agenda'
import { Atividades } from '@/pages/Atividades'
import { Dashboard } from '@/pages/Dashboard'
import { Financeiro } from '@/pages/Financeiro'
import { Login } from '@/pages/Login'
import { MinhaAgenda } from '@/pages/MinhaAgenda'
import { Pacientes } from '@/pages/Pacientes'
import { Reposicoes } from '@/pages/Reposicoes'
import { RaizRedirect } from '@/pages/RaizRedirect'

export const router = createBrowserRouter([
  {
    // O AuthProvider fica dentro do router para que Login e RequireAuth
    // possam usar navegação e compartilhar a mesma sessão.
    element: <AuthProvider />,
    children: [
      { path: '/login', element: <Login /> },
      {
        element: <RequireAuth />,
        children: [
          {
            path: '/',
            element: <AppLayout />,
            children: [
              { index: true, element: <RaizRedirect /> },
              { path: 'dashboard', element: <Dashboard /> },
              { path: 'agenda', element: <Agenda /> },
              { path: 'minha-agenda', element: <MinhaAgenda /> },
              { path: 'pacientes', element: <Pacientes /> },
              { path: 'reposicoes', element: <Reposicoes /> },
              { path: 'atividades', element: <Atividades /> },
              { path: 'financeiro', element: <Financeiro /> },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
