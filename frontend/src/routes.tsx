import { createBrowserRouter, Navigate } from 'react-router-dom'

import { AppLayout } from '@/components/layout/AppLayout'
import { Agenda } from '@/pages/Agenda'
import { Atividades } from '@/pages/Atividades'
import { Dashboard } from '@/pages/Dashboard'
import { Financeiro } from '@/pages/Financeiro'
import { Pacientes } from '@/pages/Pacientes'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'agenda', element: <Agenda /> },
      { path: 'pacientes', element: <Pacientes /> },
      { path: 'atividades', element: <Atividades /> },
      { path: 'financeiro', element: <Financeiro /> },
    ],
  },
])
