import { useState } from 'react'

import { cn } from '@/lib/cn'
import { mesCurto, reais, reaisCompacto, rotuloDeSemana } from '@/lib/formato'
import type { BaldeDeReceita, PeriodoDeAnalise, ReceitaDoPeriodo } from '@/types/dashboard'

import { AlternarTabela } from './AlternarTabela'
import { CartaoDeGrafico } from './CartaoDeGrafico'
import { Dica } from './Dica'

type Props = {
  receita: ReceitaDoPeriodo
  granularidade: PeriodoDeAnalise['granularidade']
  className?: string
}

/** Menor 1, 2 ou 5 × 10^n que cobre `valor` — o topo "redondo" do eixo. */
function tetoRedondo(valor: number): number {
  if (valor <= 0) return 0
  const potencia = 10 ** Math.floor(Math.log10(valor))
  const passo = [1, 2, 5, 10].find((m) => m * potencia >= valor) ?? 10
  return passo * potencia
}

// Posição das três linhas de grade (topo, metade, base) e de seus rótulos.
const GRADE = [
  { classe: 'top-0', fracao: 1 },
  { classe: 'top-1/2', fracao: 0.5 },
  { classe: 'top-full', fracao: 0 },
] as const

/**
 * Receita recebida ao longo do período, uma coluna por mês (ou por semana,
 * em "Este mês"). O balde corrente aparece esmaecido: ainda está crescendo, e
 * compará-lo de igual para igual com um mês fechado engana.
 */
export function ReceitaNoTempo({ receita, granularidade, className }: Props) {
  const [emTabela, setEmTabela] = useState(false)
  const { serie } = receita

  const rotulo = (b: BaldeDeReceita) =>
    granularidade === 'mes' ? mesCurto(b.inicio) : rotuloDeSemana(b.inicio, b.fim)

  // No eixo, com mais de seis meses a coluna fica com ~30px e "ago/26" não
  // cabe: vai só o mês, com o ano no primeiro balde e em janeiro. O rótulo
  // completo continua na dica e na tabela.
  const eixoCurto = granularidade === 'mes' && serie.length > 6
  const rotuloDoEixo = (b: BaldeDeReceita, i: number) =>
    eixoCurto ? mesCurto(b.inicio, i === 0 || b.inicio.slice(5, 7) === '01') : rotulo(b)

  const maximo = Math.max(0, ...serie.map((b) => b.recebido_centavos))
  const teto = tetoRedondo(maximo)
  const iMaior = serie.findIndex((b) => b.recebido_centavos === maximo)
  const iUltimo = serie.length - 1
  // Valor escrito sobre a barra: a maior e a corrente. Vizinhas, os dois
  // rótulos se atropelam — fica só o da maior (o corrente está na dica).
  const comValor = (i: number) => i === iMaior || (i === iUltimo && iUltimo - iMaior !== 1)
  const melhor = serie[iMaior]
  const unidade = granularidade === 'mes' ? 'mês' : 'semana'

  const manchete = melhor
    ? `${reais(receita.recebido_centavos)} recebidos no período · Melhor ${unidade}: ${rotulo(
        melhor,
      )}, ${reaisCompacto(melhor.recebido_centavos)}`
    : undefined

  const soma = (tipo: keyof BaldeDeReceita['por_tipo']) =>
    serie.reduce((s, b) => s + b.por_tipo[tipo], 0)

  return (
    <CartaoDeGrafico
      titulo="Receita no tempo"
      manchete={manchete}
      acao={<AlternarTabela emTabela={emTabela} onAlternar={() => setEmTabela((v) => !v)} />}
      vazio={receita.recebido_centavos === 0 ? 'Nenhum pagamento recebido no período.' : null}
      className={className}
    >
      {emTabela ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[15px]">
            <caption className="sr-only">
              Receita recebida por {unidade}, separada por tipo de cobrança
            </caption>
            <thead className="bg-subtle text-sm text-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Período</th>
                <th className="px-3 py-2 text-right font-medium">Mensalidades</th>
                <th className="px-3 py-2 text-right font-medium">Pacotes</th>
                <th className="px-3 py-2 text-right font-medium">Avulsas</th>
                <th className="px-3 py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {serie.map((b) => (
                <tr key={b.inicio} className="border-t border-edge">
                  <td className="whitespace-nowrap px-3 py-2">
                    {rotulo(b)}
                    {b.em_andamento && <span className="text-sm text-muted"> (parcial)</span>}
                  </td>
                  <td className="px-3 py-2 text-right">{reais(b.por_tipo.mensalidade)}</td>
                  <td className="px-3 py-2 text-right">{reais(b.por_tipo.pacote)}</td>
                  <td className="px-3 py-2 text-right">{reais(b.por_tipo.avulsa)}</td>
                  <td className="px-3 py-2 text-right font-medium">
                    {reais(b.recebido_centavos)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="tabular-nums">
              <tr className="border-t border-edge font-medium">
                <td className="px-3 py-2">Total</td>
                <td className="px-3 py-2 text-right">{reais(soma('mensalidade'))}</td>
                <td className="px-3 py-2 text-right">{reais(soma('pacote'))}</td>
                <td className="px-3 py-2 text-right">{reais(soma('avulsa'))}</td>
                <td className="px-3 py-2 text-right">{reais(receita.recebido_centavos)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <div className="pt-6">
          <div className="relative h-52">
            {GRADE.map((g) => (
              <div key={g.classe} aria-hidden>
                <span
                  className={cn(
                    'absolute left-0 w-16 -translate-y-1/2 pr-2 text-right text-xs tabular-nums text-muted',
                    g.classe,
                  )}
                >
                  {reaisCompacto(teto * g.fracao)}
                </span>
                <span
                  className={cn(
                    'absolute left-16 right-0 border-t',
                    g.classe,
                    g.fracao === 0 ? 'border-ink/25' : 'border-edge',
                  )}
                />
              </div>
            ))}

            <div className="absolute inset-y-0 left-16 right-0 flex items-end gap-1 px-1">
              {serie.map((b, i) => {
                const parcial = b.em_andamento ? ' (parcial)' : ''
                return (
                  <Dica
                    key={b.inicio}
                    rotulo={`${rotulo(b)}${parcial}: ${reais(b.recebido_centavos)} recebidos`}
                    titulo={`${rotulo(b)}${parcial}`}
                    linhas={[
                      { valor: reais(b.recebido_centavos), rotulo: 'no total' },
                      { valor: reais(b.por_tipo.mensalidade), rotulo: 'Mensalidades' },
                      { valor: reais(b.por_tipo.pacote), rotulo: 'Pacotes' },
                      { valor: reais(b.por_tipo.avulsa), rotulo: 'Avulsas' },
                    ]}
                    alinhamento={i === 0 ? 'inicio' : i === iUltimo ? 'fim' : 'centro'}
                    className="flex h-full min-w-0 flex-1 items-end justify-center rounded"
                  >
                    <div
                      className="relative w-full max-w-[24px]"
                      style={{ height: `${teto > 0 ? (100 * b.recebido_centavos) / teto : 0}%` }}
                    >
                      <div
                        className={cn(
                          'h-full w-full origin-bottom rounded-t motion-safe:animate-crescer-y',
                          b.em_andamento ? 'bg-brand/40' : 'bg-brand',
                        )}
                        style={{ animationDelay: `${i * 60}ms` }}
                      />
                      {comValor(i) && b.recebido_centavos > 0 && (
                        <span className="absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap text-xs font-medium tabular-nums text-ink">
                          {reaisCompacto(b.recebido_centavos)}
                        </span>
                      )}
                    </div>
                  </Dica>
                )
              })}
            </div>
          </div>

          <div className="ml-16 mt-2 flex gap-1 px-1" aria-hidden>
            {serie.map((b, i) => (
              <div
                key={b.inicio}
                className="min-w-0 flex-1 text-center text-xs leading-tight text-muted"
              >
                <span className="block whitespace-nowrap">{rotuloDoEixo(b, i)}</span>
                {b.em_andamento && <span className="block">parcial</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </CartaoDeGrafico>
  )
}
