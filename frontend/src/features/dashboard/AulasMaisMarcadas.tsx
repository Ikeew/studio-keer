import { contagem, fatia, percentual } from '@/lib/formato'
import type { ServicoNoPeriodo } from '@/types/dashboard'

import { BarraRanqueada } from './BarraRanqueada'
import { CartaoDeGrafico } from './CartaoDeGrafico'
import { listaComE } from './texto'

type Props = { servicos: ServicoNoPeriodo[]; className?: string }

/**
 * Quais aulas são mais marcadas. A barra usa a cor do próprio serviço — a
 * mesma da legenda da Agenda —, única cor que vem da API e não de token.
 */
export function AulasMaisMarcadas({ servicos, className }: Props) {
  const total = servicos.reduce((s, sv) => s + sv.reservas, 0)
  const topo = servicos[0]?.reservas ?? 0
  const lideres = servicos.filter((sv) => sv.reservas === topo && topo > 0)

  const manchete =
    lideres.length > 1
      ? `Empate entre ${listaComE(lideres.map((sv) => sv.nome))}`
      : lideres[0]
        ? `${lideres[0].nome} concentra ${percentual(
            fatia(lideres[0].reservas, total),
          )} das reservas`
        : undefined

  return (
    <CartaoDeGrafico
      titulo="Aulas mais marcadas"
      manchete={manchete}
      nota={total > 0 ? `${contagem(total, 'reserva', 'reservas')} no período` : undefined}
      vazio={total === 0 ? 'Nenhuma reserva no período.' : null}
      className={className}
    >
      <ul className="flex flex-col gap-5">
        {servicos.map((sv, i) => (
          <BarraRanqueada
            key={sv.service_id}
            indice={i}
            nome={sv.nome}
            largura={total > 0 ? (100 * sv.reservas) / total : 0}
            cor={sv.cor}
            valor={contagem(sv.reservas, 'reserva', 'reservas')}
            detalhe={`${contagem(sv.sessoes, 'turma', 'turmas')} · ${sv.ocupacao_percentual}% de ocupação`}
          />
        ))}
      </ul>
    </CartaoDeGrafico>
  )
}
