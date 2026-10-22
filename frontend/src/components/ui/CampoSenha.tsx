import { Eye, EyeOff } from 'lucide-react'
import type { InputHTMLAttributes } from 'react'
import { forwardRef, useState } from 'react'

import { cn } from '@/lib/cn'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

/**
 * Campo de senha com o olho para mostrar o que foi digitado.
 *
 * Todo campo de senha do sistema usa este componente — inclusive os que
 * vierem depois (cadastro de usuário, troca de senha), para o botão não
 * existir numa tela e faltar na outra.
 */
export const CampoSenha = forwardRef<HTMLInputElement, Props>(function CampoSenha(
  { className, ...props },
  ref,
) {
  const [visivel, setVisivel] = useState(false)
  const Icone = visivel ? EyeOff : Eye

  return (
    <div className="relative">
      <input
        ref={ref}
        {...props}
        type={visivel ? 'text' : 'password'}
        className={cn(
          'w-full rounded-card border border-edge py-3 pl-4 pr-12 outline-none focus:border-brand',
          className,
        )}
      />
      <button
        type="button"
        onClick={() => setVisivel((v) => !v)}
        aria-label={visivel ? 'Ocultar senha' : 'Mostrar senha'}
        aria-pressed={visivel}
        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-2 text-muted transition-colors hover:text-ink"
      >
        <Icone size={18} aria-hidden />
      </button>
    </div>
  )
})
