import { useState } from 'react'

import { cn } from '@/lib/cn'
import { contagem } from '@/lib/formato'
import type { CelulaDeHorario, HorariosDoPeriodo } from '@/types/dashboard'

import { AlternarTabela } from './AlternarTabela'
import { CartaoDeGrafico } from './CartaoDeGrafico'
import { Dica } from './Dica'
import { diaCurto, horaCurta } from './texto'

type Props = { horarios: HorariosDoPeriodo; className?: string }

// Degraus sequenciais de um matiz só. Classes literais: o JIT do Tailwind não
// enxerga classe montada por interpolação.
const DEGRAUS = [
  { ate: 20, classe: 'bg-brand/15', rotulo: '0–20%' },
  { ate: 40, classe: 'bg-brand/35', rotulo: '21–40%' },
  { ate: 60, classe: 'bg-brand/55', rotulo: '41–60%' },
  { ate: 80, classe: 'bg-brand/75', rotulo: '61–80%' },
  { ate: 100, classe: 'bg-brand', rotulo: '81–100%' },
] as const

function degrau(ocupacao: number): string {
  return (DEGRAUS.find((d) => ocupacao <= d.ate) ?? DEGRAUS[4]).classe
}

function lugares(c: CelulaDeHorario): string {
  return `${c.reservas} de ${c.capacidade} lugares`
}

/**
 * Mapa de calor dia × hora pela ocupação. Mostra onde a pressão de vaga se
 * concentra — é onde o overbooking acontecia.
 */
export function HorariosDePico({ horarios, className }: Props) {
  const [emTabela, setEmTabela] = useState(false)
  const { dias, horas, celulas, horas_por_dia } = horarios

  const porChave = new Map(celulas.map((c) => [`${c.dia_semana}-${c.hora}`, c]))
  // Hora aberta sem turma é capacidade que ninguém comprou; hora fora da
  // janela é o studio fechado — pintar as duas igual faria o fechado parecer
  // ociosidade.
  const abertas = new Map(dias.map((d) => [d, new Set(horas_por_dia[d] ?? [])]))
  const ordemDoDia = new Map(dias.map((d, i) => [d, i]))

  const maisCheios = [...celulas]
    .sort(
      (a, b) =>
        b.ocupacao_percentual - a.ocupacao_percentual ||
        b.reservas - a.reservas ||
        (ordemDoDia.get(a.dia_semana) ?? 0) - (ordemDoDia.get(b.dia_semana) ?? 0) ||
        a.hora - b.hora,
    )
    .slice(0, 3)
  const pico = maisCheios[0]

  const naOrdem = [...celulas].sort(
    (a, b) =>
      (ordemDoDia.get(a.dia_semana) ?? 0) - (ordemDoDia.get(b.dia_semana) ?? 0) ||
      a.hora - b.hora,
  )

  return (
    <CartaoDeGrafico
      titulo="Horários de pico"
      manchete={
        pico
          ? `Pico: ${diaCurto(pico.dia_semana)} às ${horaCurta(pico.hora)}, ${pico.ocupacao_percentual}% de ocupação`
          : undefined
      }
      acao={<AlternarTabela emTabela={emTabela} onAlternar={() => setEmTabela((v) => !v)} />}
      vazio={celulas.length === 0 ? 'Nenhuma turma no período.' : null}
      className={className}
    >
      {emTabela ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[15px]">
            <caption className="sr-only">Ocupação por dia da semana e horário</caption>
            <thead className="bg-subtle text-sm text-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Dia</th>
                <th className="px-3 py-2 text-left font-medium">Hora</th>
                <th className="px-3 py-2 text-right font-medium">Turmas</th>
                <th className="px-3 py-2 text-right font-medium">Reservas</th>
                <th className="px-3 py-2 text-right font-medium">Lugares</th>
                <th className="px-3 py-2 text-right font-medium">Ocupação</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {naOrdem.map((c) => (
                <tr key={`${c.dia_semana}-${c.hora}`} className="border-t border-edge">
                  <td className="px-3 py-2">{diaCurto(c.dia_semana)}</td>
                  <td className="px-3 py-2">{horaCurta(c.hora)}</td>
                  <td className="px-3 py-2 text-right">{c.sessoes}</td>
                  <td className="px-3 py-2 text-right">{c.reservas}</td>
                  <td className="px-3 py-2 text-right">{c.capacidade}</td>
                  <td className="px-3 py-2 text-right font-medium">
                    {c.ocupacao_percentual}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        // Lista ao lado só onde o card é largo: em lg o painel é uma coluna;
        // em xl o card divide a linha (7/12) e, com a sidebar de 280px, a
        // grade ficaria com ~260px — a lista desce e vira três colunas.
        <div className="flex flex-col gap-6 lg:flex-row xl:flex-col 2xl:flex-row">
          <div className="min-w-0 flex-1">
            {/* Rolagem só horizontal e só em tela estreita; nunca vertical. */}
            <div className="overflow-x-auto pb-1 sm:overflow-visible">
              <div
                className="grid min-w-[18rem] gap-[2px]"
                style={{
                  gridTemplateColumns: `auto repeat(${dias.length}, minmax(2rem, 1fr))`,
                }}
              >
                <span aria-hidden />
                {dias.map((d) => (
                  <span key={d} className="pb-1 text-center text-xs text-muted" aria-hidden>
                    {diaCurto(d)}
                  </span>
                ))}

                {horas.map((h, linha) => (
                  <div key={h} className="contents">
                    <span
                      className="pr-2 text-right text-xs leading-7 tabular-nums text-muted"
                      aria-hidden
                    >
                      {horaCurta(h)}
                    </span>
                    {dias.map((d, coluna) => {
                      // Sessão manda: mesmo fora da janela atual ela aconteceu
                      // (a configuração pode ter mudado depois).
                      const c = porChave.get(`${d}-${h}`)
                      if (!c && !abertas.get(d)?.has(h)) {
                        return (
                          <span
                            key={d}
                            role="img"
                            aria-label={`${diaCurto(d)} ${horaCurta(h)}: fechado`}
                            className="h-7 rounded-sm"
                          />
                        )
                      }
                      if (!c) {
                        return (
                          <span
                            key={d}
                            role="img"
                            aria-label={`${diaCurto(d)} ${horaCurta(h)}: sem turma`}
                            className="flex h-7 items-center justify-center rounded-sm bg-subtle text-xs text-muted"
                          >
                            –
                          </span>
                        )
                      }
                      const titulo = `${diaCurto(d)} ${horaCurta(h)}`
                      return (
                        <Dica
                          key={d}
                          rotulo={`${titulo}: ${c.ocupacao_percentual}% de ocupação, ${lugares(
                            c,
                          )}, ${contagem(c.sessoes, 'turma', 'turmas')}`}
                          titulo={titulo}
                          linhas={[
                            { valor: `${c.ocupacao_percentual}%`, rotulo: 'de ocupação' },
                            { valor: `${c.reservas} de ${c.capacidade}`, rotulo: 'lugares' },
                            { valor: String(c.sessoes), rotulo: c.sessoes === 1 ? 'turma' : 'turmas' },
                          ]}
                          // Abaixo de sm o overflow-x-auto também corta na
                          // vertical: a dica das três primeiras linhas (~4
                          // linhas de texto) só cabe abrindo para baixo.
                          lado={linha < 3 ? 'baixo' : 'cima'}
                          alinhamento={
                            coluna < 2 ? 'inicio' : coluna >= dias.length - 2 ? 'fim' : 'centro'
                          }
                          // Até 78 células: fora da ordem de Tab. O teclado
                          // tem o "Ver tabela", que vem antes no cabeçalho.
                          focavel={false}
                          className={cn('h-7 rounded-sm', degrau(c.ocupacao_percentual))}
                        />
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>

            <ul className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
              {DEGRAUS.map((d) => (
                <li key={d.rotulo} className="flex items-center gap-1.5">
                  <span className={cn('h-3 w-5 rounded-sm', d.classe)} aria-hidden />
                  {d.rotulo}
                </li>
              ))}
              <li className="flex items-center gap-1.5">
                <span
                  className="flex h-3 w-5 items-center justify-center rounded-sm bg-subtle leading-none"
                  aria-hidden
                >
                  –
                </span>
                Sem turma
              </li>
              <li className="flex items-center gap-1.5">
                <span className="h-3 w-5 rounded-sm border border-edge" aria-hidden />
                Fechado
              </li>
            </ul>
          </div>

          <div className="lg:w-44 lg:shrink-0 xl:w-auto 2xl:w-44">
            <h4 className="text-sm text-muted">Horários mais cheios</h4>
            <ol className="mt-3 flex flex-col gap-3 xl:grid xl:grid-cols-3 2xl:flex">
              {maisCheios.map((c, i) => (
                <li key={`${c.dia_semana}-${c.hora}`} className="flex gap-3">
                  <span className="font-heading text-sm font-semibold text-brand">{i + 1}</span>
                  <span>
                    <span className="block text-[15px] font-medium">
                      {diaCurto(c.dia_semana)} {horaCurta(c.hora)} · {c.ocupacao_percentual}%
                    </span>
                    <span className="block text-sm tabular-nums text-muted">{lugares(c)}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </CartaoDeGrafico>
  )
}
