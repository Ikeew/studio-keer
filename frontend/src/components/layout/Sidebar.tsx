import { Activity, Calendar, DollarSign, LayoutGrid, Users } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/cn'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { to: '/agenda', label: 'Agendamentos', icon: Calendar },
  // Os prints dizem "Clientes"; a nomenclatura acordada da interface é
  // "Paciente". Ver referencia-figma/README.md.
  { to: '/pacientes', label: 'Pacientes', icon: Users },
  { to: '/atividades', label: 'Atividades', icon: Activity },
  { to: '/financeiro', label: 'Financeiro', icon: DollarSign },
] as const

export function Sidebar() {
  return (
    <aside className="flex w-[280px] shrink-0 flex-col bg-brand text-white">
      <div className="border-b border-white/10 px-6 py-7">
        <h1 className="font-heading text-xl font-semibold leading-tight text-white">
          Studio Keer
        </h1>
        <p className="mt-1 text-sm text-white/70">Gestão de Agendamentos</p>
      </div>

      <nav className="flex flex-col gap-1 p-4">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-card px-4 py-3 text-[15px] transition-colors',
                isActive
                  ? 'bg-brand-dark font-medium text-white'
                  : 'text-white/85 hover:bg-white/10',
              )
            }
          >
            <Icon size={20} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
