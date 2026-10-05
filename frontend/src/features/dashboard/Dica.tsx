import type { CSSProperties, ReactNode } from 'react'

import { cn } from '@/lib/cn'

export type LinhaDaDica = { valor: string; rotulo: string }

type Props = {
  /** Texto lido pelo leitor de tela; a dica visual é só reforço. */
  rotulo: string
  titulo?: string
  linhas: LinhaDaDica[]
  children?: ReactNode
  className?: string
  style?: CSSProperties
  /** "baixo" para marcas no topo de um container que corta o que vaza. */
  lado?: 'cima' | 'baixo'
  /** "inicio"/"fim" nas bordas, para a dica não vazar para fora da página. */
  alinhamento?: 'centro' | 'inicio' | 'fim'
  /**
   * false tira a marca da ordem de Tab. Para grades densas (o mapa de calor
   * chegava a 78 paradas): quem usa teclado lê os mesmos números na tabela.
   */
  focavel?: boolean
}

/**
 * Dica leve ao passar o mouse ou focar uma marca de gráfico.
 *
 * Nunca é o único jeito de ler um valor: todo gráfico tem lista, legenda ou
 * tabela com os mesmos números visíveis. Por isso o painel é `aria-hidden` —
 * o leitor de tela já ouve o `rotulo` da marca.
 */
export function Dica({
  rotulo,
  titulo,
  linhas,
  children,
  className,
  style,
  lado = 'cima',
  alinhamento = 'centro',
  focavel = true,
}: Props) {
  return (
    <div
      role="img"
      aria-label={rotulo}
      tabIndex={focavel ? 0 : undefined}
      style={style}
      className={cn(
        'group relative outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2',
        className,
      )}
    >
      {children}
      <div
        aria-hidden
        className={cn(
          'pointer-events-none invisible absolute z-20 whitespace-nowrap rounded-card bg-ink px-3 py-2 text-left text-sm text-white opacity-0 shadow-card transition-opacity duration-150',
          'group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100',
          lado === 'cima' ? 'bottom-full mb-2' : 'top-full mt-2',
          alinhamento === 'centro' && 'left-1/2 -translate-x-1/2',
          alinhamento === 'inicio' && 'left-0',
          alinhamento === 'fim' && 'right-0',
        )}
      >
        {titulo && <p className="mb-1 text-xs text-white/70">{titulo}</p>}
        {linhas.map((l) => (
          <p key={l.rotulo} className="tabular-nums">
            <span className="font-medium">{l.valor}</span>{' '}
            <span className="text-white/70">{l.rotulo}</span>
          </p>
        ))}
      </div>
    </div>
  )
}
