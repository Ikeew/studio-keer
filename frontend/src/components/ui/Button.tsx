import type { ButtonHTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'primario' | 'secundario' | 'acento'
}

export function Button({ variante = 'primario', className, ...props }: Props) {
  return (
    <button
      {...props}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-card px-5 py-3 text-[15px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        variante === 'primario' && 'bg-brand text-white hover:bg-brand-dark',
        variante === 'secundario' && 'bg-edge text-ink hover:bg-edge/70',
        variante === 'acento' && 'bg-accent text-white hover:opacity-90',
        className,
      )}
    />
  )
}
