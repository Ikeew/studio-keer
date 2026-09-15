import {
  Activity,
  Calendar,
  CalendarClock,
  Clock,
  DollarSign,
  LayoutGrid,
  LogOut,
  Users,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { podeAcessar } from '@/auth/permissoes'
import { useAuth } from '@/auth/useAuth'
import { cn } from '@/lib/cn'
import { PAPEL_LABEL } from '@/types/auth'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  // Só o instrutor enxerga: é a tela dele, com as aulas de hoje.
  { to: '/minha-agenda', label: 'Minha Agenda', icon: Clock },
  { to: '/agenda', label: 'Agendamentos', icon: Calendar },
  // Os prints dizem "Clientes"; a nomenclatura acordada da interface é
  // "Paciente". Ver referencia-figma/README.md.
  // Logo abaixo da agenda: é onde a recepção resolve o que hoje fica na
  // cabeça da proprietária.
  { to: '/reposicoes', label: 'Reposições', icon: CalendarClock },
  { to: '/pacientes', label: 'Pacientes', icon: Users },
  { to: '/atividades', label: 'Atividades', icon: Activity },
  { to: '/financeiro', label: 'Financeiro', icon: DollarSign },
] as const

export function Sidebar() {
  const { usuario, sair } = useAuth()
  if (!usuario) return null

  const itens = NAV.filter((item) => podeAcessar(usuario.papel, item.to))

  return (
    <aside aria-label="Menu principal" className="flex w-[280px] shrink-0 flex-col bg-brand text-white">
      <div className="border-b border-white/10 px-6 py-7">
        {/* Mantemos como <span> para não conflitar com o <h1> de cada página. */}
        <span className="font-heading text-xl font-semibold leading-tight text-white">
          Studio Keer
        </span>
        <p className="mt-1 text-sm text-white/70">Gestão de Agendamentos</p>
      </div>

      <nav aria-label="Navegação" className="flex flex-col gap-1 p-4">
        {itens.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-card px-4 py-3 text-[15px] transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-1 focus-visible:ring-offset-brand',
                isActive
                  ? 'bg-brand-dark font-medium text-white'
                  : 'text-white/85 hover:bg-white/10',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={20} strokeWidth={2} aria-hidden="true" />
                {label}
                {/* Anuncia "página atual" para leitores de tela sem alterar visual. */}
                {isActive && <span className="sr-only"> (página atual)</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto border-t border-white/10 p-4">
        <p className="truncate text-[15px] font-medium text-white">{usuario.nome}</p>
        <p className="text-sm text-white/70">{PAPEL_LABEL[usuario.papel]}</p>
        <button
          type="button"
          onClick={sair}
          className="mt-3 flex w-full items-center gap-2 rounded-card px-3 py-2 text-sm text-white/85 transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-1 focus-visible:ring-offset-brand"
        >
          <LogOut size={16} aria-hidden="true" />
          Sair
        </button>
      </div>
    </aside>
  )
}
