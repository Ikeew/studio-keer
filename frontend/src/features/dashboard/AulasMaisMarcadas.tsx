import { useState } from 'react'

import { cn } from '@/lib/cn'
import { contagem, fatia, percentual } from '@/lib/formato'
import type { ServicoNoPeriodo } from '@/types/dashboard'

import { BarraRanqueada } from './BarraRanqueada'
import { CartaoDeGrafico } from './CartaoDeGrafico'
import { listaComE } from './texto'

type Props = { servicos: ServicoNoPeriodo[]; className?: string }

/**
 * Marcadas é demanda (toda reserva ativa, inclusive as futuras e as faltas);
 * realizadas é o que foi entregue (presença registrada).
 */
type Metrica = 'marcadas' | 'realizadas'

const TEXTO: Record<
  Metrica,
  { titulo: string; singular: string; plural: string; sufixo: string; vazio: string }
> = {
  marcadas: {
    titulo: 'Aulas mais marcadas',
    singular: 'reserva',
    plural: 'reservas',
    sufixo: 'das reservas',
    vazio: 'Nenhuma reserva no período.',
  },
  realizadas: {
    titulo: 'Aulas mais realizadas',
    singular: 'aula realizada',
    plural: 'aulas realizadas',
    sufixo: 'das aulas realizadas',
    vazio: 'Nenhuma presença registrada no período.',
  },
}

const valorDe = (sv: ServicoNoPeriodo, m: Metrica) => (m === 'marcadas' ? sv.reservas : sv.realizadas)

function SeletorDeMetrica({ metrica, onMudar }: { metrica: Metrica; onMudar: (m: Metrica) => void }) {
  return (
    <div role="group" aria-label="O que contar" className="flex shrink-0 rounded-card bg-subtle p-1">
      {(['marcadas', 'realizadas'] as const).map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={metrica === m}
          onClick={() => onMudar(m)}
          className={cn(
            'rounded px-3 py-1 text-sm font-medium capitalize transition-colors',
            metrica === m ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink',
          )}
        >
          {m}
        </button>
      ))}
    </div>
  )
}

/**
 * Quais aulas são mais marcadas — ou mais realizadas. A barra usa a cor do
 * próprio serviço — a mesma da legenda da Agenda —, única cor que vem da API
 * e não de token.
 */
export function AulasMaisMarcadas({ servicos, className }: Props) {
  const [metrica, setMetrica] = useState<Metrica>('marcadas')
  const texto = TEXTO[metrica]

  // A API ordena por marcadas; para realizadas a ordem é refeita aqui.
  const ordenados = [...servicos].sort(
    (a, b) => valorDe(b, metrica) - valorDe(a, metrica) || a.nome.localeCompare(b.nome),
  )
  const total = ordenados.reduce((s, sv) => s + valorDe(sv, metrica), 0)
  const topo = ordenados[0] ? valorDe(ordenados[0], metrica) : 0
  const lideres = ordenados.filter((sv) => valorDe(sv, metrica) === topo && topo > 0)
  // O cartão vazio esconde a ação: só vale quando não há reserva nenhuma, para
  // o seletor não sumir ao trocar para "realizadas" num período sem presença.
  const semReservas = servicos.every((sv) => sv.reservas === 0)

  const manchete =
    lideres.length > 1
      ? `Empate entre ${listaComE(lideres.map((sv) => sv.nome))}`
      : lideres[0]
        ? `${lideres[0].nome} concentra ${percentual(fatia(topo, total))} ${texto.sufixo}`
        : undefined

  return (
    <CartaoDeGrafico
      titulo={texto.titulo}
      manchete={manchete}
      nota={total > 0 ? `${contagem(total, texto.singular, texto.plural)} no período` : undefined}
      acao={<SeletorDeMetrica metrica={metrica} onMudar={setMetrica} />}
      vazio={semReservas ? TEXTO.marcadas.vazio : null}
      className={className}
    >
      {total === 0 && (
        <p className="py-10 text-center text-[15px] text-muted">{texto.vazio}</p>
      )}
      <ul className={cn('flex flex-col gap-5', total === 0 && 'hidden')}>
        {ordenados.map((sv, i) => (
          <BarraRanqueada
            key={sv.service_id}
            indice={i}
            nome={sv.nome}
            largura={total > 0 ? (100 * valorDe(sv, metrica)) / total : 0}
            cor={sv.cor}
            valor={contagem(valorDe(sv, metrica), texto.singular, texto.plural)}
            detalhe={`${contagem(sv.sessoes, 'turma', 'turmas')} · ${sv.ocupacao_percentual}% de ocupação`}
          />
        ))}
      </ul>
    </CartaoDeGrafico>
  )
}
