import type { ReactNode } from 'react'

import { cn } from '@/lib/cn'

type Props = {
  nome: string
  /** Largura do preenchimento, 0..100. */
  largura: number
  /** Classe de cor do preenchimento (token). */
  corClasse?: string
  /** Cor vinda da API (cor do serviço) — a única exceção aos tokens. */
  cor?: string
  /** Valor principal à direita, ex.: "46%". */
  valor: ReactNode
  /** Detalhe abaixo do valor, ex.: "23 · R$ 4.140,00". */
  detalhe?: ReactNode
  /** Posição na lista, para escalonar a animação. */
  indice: number
}

/**
 * Uma linha de lista ranqueada: nome, barra sobre trilho e os números
 * visíveis à direita. A barra reforça; o valor escrito é o que se lê.
 */
export function BarraRanqueada({
  nome,
  largura,
  corClasse,
  cor,
  valor,
  detalhe,
  indice,
}: Props) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-6 gap-y-2">
      <span className="truncate text-[15px]">{nome}</span>
      <span className="row-span-2 text-right">
        <span className="block font-medium tabular-nums">{valor}</span>
        {detalhe && <span className="block text-sm tabular-nums text-muted">{detalhe}</span>}
      </span>
      <span className="block h-2.5 overflow-hidden rounded-full bg-grafico-trilho" aria-hidden>
        <span
          className={cn(
            'block h-full origin-left rounded-full motion-safe:animate-crescer-x',
            corClasse,
          )}
          style={{
            width: `${Math.max(0, Math.min(100, largura))}%`,
            backgroundColor: cor,
            animationDelay: `${indice * 60}ms`,
          }}
        />
      </span>
    </li>
  )
}
