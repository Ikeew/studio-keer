import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'
import { forwardRef } from 'react'

import { cn } from '@/lib/cn'

const BASE =
  'w-full rounded-card border border-edge px-4 py-3 text-[15px] outline-none transition-colors focus:border-brand disabled:bg-subtle'

type WrapProps = {
  label: string
  erro?: string
  obrigatorio?: boolean
  children: ReactNode
  id: string
}

export function Campo({ label, erro, obrigatorio, children, id }: WrapProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
        {obrigatorio && <span className="text-danger"> *</span>}
      </label>
      {children}
      {erro && (
        <p id={`erro-${id}`} className="mt-1 text-sm text-danger">
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
