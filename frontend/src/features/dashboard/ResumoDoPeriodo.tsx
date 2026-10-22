import { cn } from '@/lib/cn'
import { contagem, reais } from '@/lib/formato'
import type { Analise } from '@/types/dashboard'

type Props = { analise: Analise; className?: string }

type Numero = { rotulo: string; valor: string; contexto: string; titulo?: string }

// Divisores finos entre os quatro números: em 2 colunas, linha vertical no
// meio e horizontal entre as fileiras; em 4 colunas, só verticais.
// As 4 colunas só entram em xl: a sidebar fixa de 280px come a largura que o
// `lg` supõe existir, e um valor em reais não cabe numa célula de ~120px.
const DIVISOR = [
  '',
  'border-l border-edge',
  'border-t border-edge xl:border-l xl:border-t-0',
  'border-l border-t border-edge xl:border-t-0',
] as const

/** Os quatro números do período num card só, sem ícone — o número é o destaque. */
export function ResumoDoPeriodo({ analise, className }: Props) {
  const { receita, ocupacao, presenca, origens } = analise
  // Denominador do comparecimento: só reservas com presença ou falta
  // registrada ("sem registro" fica fora, como no backend). Zero registros
  // mostra "—": o 0% do contrato afirmaria uma ausência total que não houve.
  const registradas =
    presenca.presentes + presenca.faltas_justificadas + presenca.faltas_nao_justificadas
  const reposicoes = origens.find((o) => o.origem === 'reposicao')?.reservas ?? 0
  const pagamentos = analise.formas_pagamento.reduce((s, f) => s + f.pagamentos, 0)

  const numeros: Numero[] = [
    // Valor recebido só para o admin. Os demais veem quantas baixas houve,
    // que é o que eles mesmos registraram.
    receita
      ? {
          rotulo: 'Recebido',
          valor: reais(receita.recebido_centavos),
          contexto: contagem(receita.pagamentos, 'pagamento', 'pagamentos'),
        }
      : {
          rotulo: 'Pagamentos',
          valor: pagamentos.toLocaleString('pt-BR'),
          contexto: 'registrados no período',
        },
    {
      rotulo: 'Ocupação',
      valor: `${ocupacao.percentual}%`,
      // Numerador e denominador visíveis: percentual sozinho não é auditável.
      contexto: `${ocupacao.reservas_ativas} de ${ocupacao.capacidade_ofertada} lugares`,
      titulo: ocupacao.formula,
    },
    {
      rotulo: 'Comparecimento',
      valor: registradas === 0 ? '—' : `${presenca.comparecimento_percentual}%`,
      // Registro = presença ou falta marcada numa reserva.
      contexto: `${contagem(presenca.presentes, 'presença', 'presenças')} em ${contagem(
        registradas,
        'registro',
        'registros',
      )}`,
    },
    {
      rotulo: 'Reposições',
      valor: reposicoes.toLocaleString('pt-BR'),
      contexto: `${contagem(
        presenca.faltas_justificadas,
        'falta justificada',
        'faltas justificadas',
      )} no período`,
    },
  ]

  return (
    <section
      aria-label="Resumo do período"
      className={cn(
        'grid grid-cols-2 rounded-card border border-edge bg-surface shadow-card xl:grid-cols-4',
        className,
      )}
    >
      {numeros.map((n, i) => (
        <div key={n.rotulo} className={cn('px-6 py-5', DIVISOR[i])} title={n.titulo}>
          <p className="text-sm text-muted">{n.rotulo}</p>
          {/* Tamanho pela largura da célula, não do viewport: cresce só onde
              "R$ 123.456,78" cabe (2 colunas em lg, 4 colunas em 2xl). */}
          <p className="mt-2 font-heading text-2xl font-semibold tabular-nums lg:text-3xl xl:text-2xl 2xl:text-3xl">
            {n.valor}
          </p>
          <p className="mt-1 text-sm text-muted">{n.contexto}</p>
        </div>
      ))}
    </section>
  )
}
