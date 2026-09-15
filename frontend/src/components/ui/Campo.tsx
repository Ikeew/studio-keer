import {
  Children,
  cloneElement,
  forwardRef,
  isValidElement,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'

import { cn } from '@/lib/cn'

const BASE =
  'w-full rounded-card border border-edge px-4 py-3 text-[15px] outline-none transition-colors focus:border-brand focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 disabled:bg-subtle'

type WrapProps = {
  label: string
  erro?: string
  obrigatorio?: boolean
  children: ReactNode
  id: string
}

/**
 * Campo de formulário com label, mensagem de erro e acessibilidade completa.
 *
 * Injeta automaticamente `aria-describedby` e `aria-invalid` no filho direto
 * quando há erro — sem exigir que cada formulário repita esses atributos.
 */
export function Campo({ label, erro, obrigatorio, children, id }: WrapProps) {
  const erroId = erro ? `erro-${id}` : undefined

  // Injeta aria-describedby e aria-invalid no primeiro filho que for um
  // elemento React válido (Input, Select, CampoMascarado, etc.).
  const filhoComAria = Children.map(children, (filho, index) => {
    if (index !== 0 || !isValidElement(filho)) return filho
    return cloneElement(filho as React.ReactElement<React.HTMLAttributes<HTMLElement>>, {
      'aria-describedby': erroId,
      'aria-invalid': erro ? (true as unknown as string) : undefined,
    })
  })

  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
        {obrigatorio && (
          <span className="text-danger" aria-hidden="true">
            {' '}
            *
          </span>
        )}
        {obrigatorio && <span className="sr-only"> (obrigatório)</span>}
      </label>
      {filhoComAria}
      {erro && (
        <p id={erroId} role="alert" className="mt-1 text-sm text-danger">
          {erro}
        </p>
      )}
    </div>
  )
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} {...props} className={cn(BASE, className)} />
  },
)

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, ...props }, ref) {
    return <select ref={ref} {...props} className={cn(BASE, 'bg-surface', className)} />
  },
)
