import { cn } from '@/lib/cn'
import { contagem, fatia, percentual } from '@/lib/formato'
import type { PresencaDoPeriodo } from '@/types/dashboard'

import { CartaoDeGrafico } from './CartaoDeGrafico'

type Props = { presenca: PresencaDoPeriodo; className?: string }

type Segmento = { chave: string; rotulo: string; valor: number; cor: string }

/**
 * Comparecimento nas reservas de aulas que já aconteceram. A unidade é a
 * reserva, não a aula: uma turma de 4 sem presença marcada são 4 reservas.
 * A faixa empilhada separa presença, falta justificada, falta e "sem
 * registro" — este último existe porque, se ninguém marca presença, o
 * percentual fica bonito e mente (docs/premissas.md, P8).
 */
export function Comparecimento({ presenca, className }: Props) {
  const segmentos: Segmento[] = [
    {
      chave: 'presente',
      rotulo: 'Presentes',
      valor: presenca.presentes,
      cor: 'bg-grafico-presente',
    },
    {
      chave: 'justificada',
      rotulo: 'Faltas justificadas',
      valor: presenca.faltas_justificadas,
      cor: 'bg-grafico-justificada',
    },
    {
      chave: 'falta',
      rotulo: 'Faltas',
      valor: presenca.faltas_nao_justificadas,
      cor: 'bg-falta',
    },
    {
      chave: 'sem-registro',
      rotulo: 'Sem registro',
      valor: presenca.sem_registro,
      cor: 'bg-grafico-sem-registro',
    },
  ]
  const realizadas = segmentos.reduce((s, sg) => s + sg.valor, 0)
  // O backend devolve 0% quando nada foi registrado (contrato), mas "0%" na
  // tela afirmaria que ninguém veio — o que não aconteceu.
  const registradas =
    presenca.presentes + presenca.faltas_justificadas + presenca.faltas_nao_justificadas

  return (
    <CartaoDeGrafico
      titulo="Comparecimento"
      vazio={realizadas === 0 ? 'Nenhuma reserva de aula já realizada no período.' : null}
      className={className}
    >
      {/* Em largura total (xl), o número fica à esquerda e a faixa com a
          legenda à direita — uma faixa de ~900px esticada não se lê. */}
      <div className="xl:grid xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] xl:items-center xl:gap-x-10">
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-heading text-4xl font-semibold">
            {registradas === 0 ? '—' : `${presenca.comparecimento_percentual}%`}
          </span>
          {/* O % exclui "sem registro" (contrato); os % da legenda são sobre
              todas as reservas de aulas que já aconteceram, para somarem 100%. */}
          <span className="text-[15px] text-muted">
            {registradas === 0
              ? 'nenhuma presença ou falta registrada ainda'
              : 'de comparecimento nas reservas com presença ou falta registrada'}
          </span>
        </p>

        <div className="mt-5 xl:mt-0">
          <div
            aria-hidden
            className="flex h-3 origin-left gap-[2px] overflow-hidden rounded-full bg-surface motion-safe:animate-crescer-x"
          >
            {segmentos
              .filter((sg) => sg.valor > 0)
              .map((sg) => (
                <span
                  key={sg.chave}
                  className={cn('h-full basis-0', sg.cor)}
                  style={{ flexGrow: sg.valor }}
                />
              ))}
          </div>

          <ul className="mt-5 grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            {segmentos.map((sg) => (
              <li key={sg.chave} className="flex items-center gap-3 text-[15px]">
                <span className={cn('h-3 w-3 shrink-0 rounded-sm', sg.cor)} aria-hidden />
                <span className="min-w-0 flex-1">{sg.rotulo}</span>
                <span className="tabular-nums">
                  <span className="font-medium">{sg.valor.toLocaleString('pt-BR')}</span>
                  <span className="text-sm text-muted">
                    {' '}
                    · {percentual(fatia(sg.valor, realizadas))}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {presenca.sem_registro > 0 && (
        <p className="mt-5 rounded-card bg-subtle px-4 py-3 text-sm">
          {presenca.sem_registro === 1
            ? '1 reserva de aula que já aconteceu está sem presença marcada'
            : `${presenca.sem_registro.toLocaleString('pt-BR')} reservas de aulas que já aconteceram estão sem presença marcada`}{' '}
          — registre na Agenda para o comparecimento não mentir.
        </p>
      )}

      <p className="mt-4 text-sm text-muted">
        {contagem(presenca.canceladas, 'reserva cancelada', 'reservas canceladas')} ·{' '}
        {contagem(
          presenca.a_realizar,
          'reserva ainda por acontecer',
          'reservas ainda por acontecer',
        )}
      </p>
    </CartaoDeGrafico>
  )
}
