/** ["PIX", "Crédito", "Débito"] -> "PIX, Crédito e Débito". */
export function listaComE(itens: string[]): string {
  if (itens.length <= 1) return itens[0] ?? ''
  return `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}`
}

/** Rótulo curto do dia na convenção do banco: 0 = domingo … 6 = sábado. */
export const DIA_CURTO = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'] as const

export function diaCurto(diaSemana: number): string {
  return DIA_CURTO[diaSemana] ?? String(diaSemana)
}

/** 8 -> "08h". */
export function horaCurta(hora: number): string {
  return `${String(hora).padStart(2, '0')}h`
}
