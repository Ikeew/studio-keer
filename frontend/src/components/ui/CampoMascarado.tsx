import { forwardRef, type InputHTMLAttributes } from 'react'

import { Input } from '@/components/ui/Campo'

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> & {
  mascara: (valor: string) => string
  onChange: (e: { target: { value: string; name: string } }) => void
  name: string
}

/**
 * Input que aplica máscara ao digitar.
 *
 * Reemite o evento com o valor já formatado, para o react-hook-form guardar o
 * texto que a pessoa vê. O backend normaliza para dígitos, e a busca funciona
 * com ou sem formatação — então guardar formatado não quebra nada.
 */
export const CampoMascarado = forwardRef<HTMLInputElement, Props>(function CampoMascarado(
  { mascara, onChange, name, ...props },
  ref,
) {
  return (
    <Input
      {...props}
      ref={ref}
      name={name}
      inputMode="numeric"
      onChange={(e) => onChange({ target: { value: mascara(e.target.value), name } })}
    />
  )
})
