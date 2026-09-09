import type { ReactNode } from 'react'

type Props = {
  title: string
  subtitle?: string
  action?: ReactNode
}

/** Cabeçalho de página: título, subtítulo e ação à direita (padrão dos prints). */
export function PageHeader({ title, subtitle, action }: Props) {
  return (
    <header className="mb-8 flex items-start justify-between gap-4">
      <div>
        <h1 className="font-heading text-[34px] font-semibold leading-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-muted">{subtitle}</p>}
      </div>
      {action}
    </header>
  )
}
