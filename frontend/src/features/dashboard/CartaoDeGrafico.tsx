import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'

type Props = {
  titulo: string
  /** A frase que responde à pergunta do gráfico, ex.: "PIX lidera com 46%". */
  manchete?: ReactNode
  /** Contexto secundário, abaixo da manchete. */
  nota?: ReactNode
  /** Ação à direita do título — em geral o alternador de tabela. */
  acao?: ReactNode
  /** Quando preenchido, substitui o conteúdo por este aviso. */
  vazio?: string | null
  className?: string
  children?: ReactNode
}

/** Moldura comum dos gráficos da análise, no padrão de card do projeto. */
export function CartaoDeGrafico({
  titulo,
  manchete,
  nota,
  acao,
  vazio,
  className,
  children,
}: Props) {
  return (
    <article
      className={cn(
        'flex flex-col rounded-card border border-edge bg-surface p-6 shadow-card',
        className,
      )}
    >
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-heading text-lg font-semibold">{titulo}</h3>
          {!vazio && manchete && <p className="mt-1 text-[15px] text-ink">{manchete}</p>}
          {!vazio && nota && <p className="mt-1 text-sm text-muted">{nota}</p>}
        </div>
        {!vazio && acao && <div className="shrink-0">{acao}</div>}
      </header>

      {vazio ? (
        <p className="flex flex-1 items-center justify-center py-10 text-center text-[15px] text-muted">
          {vazio}
        </p>
      ) : (
        <div className="mt-6 flex-1">{children}</div>
      )}
    </article>
  )
}
