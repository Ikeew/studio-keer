/** Centavos -> "R$ 120,00". Dinheiro trafega como inteiro, nunca float. */
export function reais(centavos: number): string {
  return (centavos / 100).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

/** "R$ 120,00" ou "120,00" -> 12000. Devolve null se não houver dígito. */
export function paraCentavos(texto: string): number | null {
  const limpo = texto.replace(/[^\d,.-]/g, '').replace(/\./g, '').replace(',', '.')
  if (!limpo) return null
  const n = Number(limpo)
  return Number.isFinite(n) ? Math.round(n * 100) : null
}

/** "11987654321" -> "(11) 98765-4321". Devolve como veio se não reconhecer. */
export function telefone(valor: string | null): string {
  if (!valor) return ''
  const d = valor.replace(/\D/g, '')
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  return valor
}

/** "2026-05-04" -> "04/05/2026", sem passar por Date (evita erro de fuso). */
export function data(iso: string | null): string {
  if (!iso) return ''
  const [ano, mes, dia] = iso.split('-')
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : iso
}

/** Iniciais para o avatar do card, como nos prints. */
export function inicial(nome: string): string {
  return nome.trim().charAt(0).toUpperCase() || '?'
}
