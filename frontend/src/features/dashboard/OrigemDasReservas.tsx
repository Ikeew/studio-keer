import { contagem, fatia, percentual } from '@/lib/formato'
import { ORIGEM_LABEL } from '@/types/agenda'
import type { ReservasPorOrigem } from '@/types/dashboard'

import { BarraRanqueada } from './BarraRanqueada'
import { CartaoDeGrafico } from './CartaoDeGrafico'

type Props = { origens: ReservasPorOrigem[]; className?: string }

/**
 * De onde vêm as reservas. A ênfase é a reposição: é ela que, encaixada de
 * cabeça, causava o overbooking — e aqui ela aparece ocupando vaga como
 * qualquer outra reserva.
 */
export function OrigemDasReservas({ origens, className }: Props) {
  const total = origens.reduce((s, o) => s + o.reservas, 0)
  const reposicoes = origens.find((o) => o.origem === 'reposicao')?.reservas ?? 0
  // Ranqueada; no empate, mantém a ordem do enum que vem da API.
  const ordenadas = [...origens].sort((a, b) => b.reservas - a.reservas)

  return (
    <CartaoDeGrafico
      titulo="Origem das reservas"
      manchete={
        reposicoes === 1
          ? '1 reposição ocupou vaga no período'
          : `${reposicoes.toLocaleString('pt-BR')} reposições ocuparam vaga no período`
      }
      nota="Reposição conta contra a capacidade como qualquer reserva."
      vazio={total === 0 ? 'Nenhuma reserva no período.' : null}
      className={className}
    >
      <ul className="flex flex-col gap-5">
        {ordenadas.map((o, i) => (
          <BarraRanqueada
            key={o.origem}
            indice={i}
            nome={ORIGEM_LABEL[o.origem]}
            largura={total > 0 ? (100 * o.reservas) / total : 0}
            corClasse={o.origem === 'reposicao' ? 'bg-brand' : 'bg-grafico-apoio'}
            valor={percentual(fatia(o.reservas, total))}
            detalhe={contagem(o.reservas, 'reserva', 'reservas')}
          />
        ))}
      </ul>
    </CartaoDeGrafico>
  )
}
