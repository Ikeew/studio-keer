import { contagem, fatia, percentual, reais } from '@/lib/formato'
import type { UsoDeFormaDePagamento } from '@/types/dashboard'
import { FORMA_LABEL } from '@/types/financeiro'

import { BarraRanqueada } from './BarraRanqueada'
import { CartaoDeGrafico } from './CartaoDeGrafico'
import { listaComE } from './texto'

type Props = { formas: UsoDeFormaDePagamento[]; className?: string }

function nomeDaForma(f: UsoDeFormaDePagamento): string {
  return f.forma ? FORMA_LABEL[f.forma] : 'Não informada'
}

/**
 * Qual forma de pagamento é a mais usada. A pergunta é de ranking, então a
 * líder ganha a cor da marca e as demais ficam em apoio.
 */
export function FormasDePagamento({ formas, className }: Props) {
  const total = formas.reduce((s, f) => s + f.pagamentos, 0)
  const topo = formas[0]?.pagamentos ?? 0
  const lideres = formas.filter((f) => f.pagamentos === topo && topo > 0)

  const manchete =
    lideres.length > 1
      ? `Empate entre ${listaComE(lideres.map(nomeDaForma))}`
      : lideres[0]
        ? `${nomeDaForma(lideres[0])} lidera com ${percentual(
            fatia(lideres[0].pagamentos, total),
          )} dos pagamentos`
        : undefined

  return (
    <CartaoDeGrafico
      titulo="Formas de pagamento"
      manchete={manchete}
      nota={total > 0 ? contagem(total, 'pagamento recebido', 'pagamentos recebidos') : undefined}
      vazio={total === 0 ? 'Nenhum pagamento registrado no período.' : null}
      className={className}
    >
      <ul className="flex flex-col gap-5">
        {formas.map((f, i) => (
          <BarraRanqueada
            key={f.forma ?? 'nao-informada'}
            indice={i}
            nome={nomeDaForma(f)}
            largura={total > 0 ? (100 * f.pagamentos) / total : 0}
            corClasse={f.pagamentos === topo ? 'bg-brand' : 'bg-grafico-apoio'}
            valor={percentual(fatia(f.pagamentos, total))}
            detalhe={
              f.valor_centavos === null
                ? String(f.pagamentos)
                : `${f.pagamentos} · ${reais(f.valor_centavos)}`
            }
          />
        ))}
      </ul>
    </CartaoDeGrafico>
  )
}
