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

/** "22/10 às 14:05", no fuso do studio. Para carimbo de quem fez o quê. */
export function dataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Sao_Paulo',
  }).replace(', ', ' às ')
}

/** Iniciais para o avatar do card, como nos prints. */
export function inicial(nome: string): string {
  return nome.trim().charAt(0).toUpperCase() || '?'
}

// ---------------------------------------------------------------------------
// Gráficos da análise. Datas por split da string ISO, nunca `new Date` — o
// mesmo motivo de `data()`: "2026-08-01" vira 31/07 no fuso de São Paulo.
// ---------------------------------------------------------------------------

const MESES_CURTOS = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
] as const

function partes(iso: string): { ano: string; mes: number; dia: number } {
  const [ano = '', mes = '', dia = ''] = iso.split('-')
  return { ano, mes: Number(mes), dia: Number(dia) }
}

function nomeDoMes(mes: number): string {
  return MESES_CURTOS[mes - 1] ?? String(mes)
}

/** Centavos -> "R$ 4,1 mil", "R$ 1,2 mi", "R$ 950". Para eixo e manchete. */
export function reaisCompacto(centavos: number): string {
  const r = centavos / 100
  const abs = Math.abs(r)
  const uma = (n: number) => n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })
  if (abs >= 1_000_000) return `R$ ${uma(r / 1_000_000)} mi`
  if (abs >= 1_000) return `R$ ${uma(r / 1_000)} mil`
  return `R$ ${Math.round(r).toLocaleString('pt-BR')}`
}

/** 46.4 -> "46%". */
export function percentual(valor: number): string {
  return `${Math.round(valor)}%`
}

/** Fatia inteira de `parte` em `total` (0..100); 0 quando o total é 0. */
export function fatia(parte: number, total: number): number {
  return total > 0 ? Math.round((100 * parte) / total) : 0
}

/** (1, "pagamento", "pagamentos") -> "1 pagamento"; (57, …) -> "57 pagamentos". */
export function contagem(n: number, singular: string, plural: string): string {
  return `${n.toLocaleString('pt-BR')} ${n === 1 ? singular : plural}`
}

/** "2026-08-01" -> "ago/26"; sem o ano, "ago". */
export function mesCurto(iso: string, comAno = true): string {
  const { ano, mes } = partes(iso)
  return comAno ? `${nomeDoMes(mes)}/${ano.slice(2)}` : nomeDoMes(mes)
}

/** ("2026-10-06", "2026-10-12") -> "06–12/10"; virando o mês, "29/09–05/10". */
export function rotuloDeSemana(inicio: string, fim: string): string {
  const a = partes(inicio)
  const b = partes(fim)
  const dd = (n: number) => String(n).padStart(2, '0')
  if (a.mes === b.mes) return `${dd(a.dia)}–${dd(b.dia)}/${dd(b.mes)}`
  return `${dd(a.dia)}/${dd(a.mes)}–${dd(b.dia)}/${dd(b.mes)}`
}

/** ("2026-08-01", "2026-10-31") -> "1 ago – 31 out 2026". */
export function intervaloDoPeriodo(inicio: string, fim: string): string {
  const a = partes(inicio)
  const b = partes(fim)
  const anoDoInicio = a.ano === b.ano ? '' : ` ${a.ano}`
  return `${a.dia} ${nomeDoMes(a.mes)}${anoDoInicio} – ${b.dia} ${nomeDoMes(b.mes)} ${b.ano}`
}
