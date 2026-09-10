/**
 * Máscaras de digitação.
 *
 * A recepção digita CPF e telefone o dia inteiro (RNF01 — usabilidade). As
 * funções formatam enquanto se digita e nunca bloqueiam o campo: o que sai
 * daqui é sempre reversível para dígitos, e o backend normaliza de novo.
 */

export function soDigitos(valor: string): string {
  return valor.replace(/\D/g, '')
}

/** '52998224725' -> '529.982.247-25', formatando parcial enquanto digita. */
export function mascaraCpf(valor: string): string {
  const d = soDigitos(valor).slice(0, 11)
  if (d.length <= 3) return d
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`
}

/**
 * '11987654321' -> '(11) 98765-4321'; 10 dígitos -> '(11) 3456-7890'.
 *
 * O corte de 9 ou 8 dígitos só é decidido no 11º: enquanto se digita, o
 * número parece fixo e vira celular no último dígito.
 */
export function mascaraTelefone(valor: string): string {
  const d = soDigitos(valor).slice(0, 11)
  if (d.length <= 2) return d.length ? `(${d}` : ''
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
}
