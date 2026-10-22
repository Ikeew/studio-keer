import { useState } from 'react'

import { useAnalise } from '@/api/dashboard'
import { cn } from '@/lib/cn'
import { intervaloDoPeriodo } from '@/lib/formato'

import { AulasMaisMarcadas } from './AulasMaisMarcadas'
import { Comparecimento } from './Comparecimento'
import { FormasDePagamento } from './FormasDePagamento'
import { HorariosDePico } from './HorariosDePico'
import { OrigemDasReservas } from './OrigemDasReservas'
import { ReceitaNoTempo } from './ReceitaNoTempo'
import { ResumoDoPeriodo } from './ResumoDoPeriodo'

const PERIODOS = [
  { meses: 1, rotulo: 'Este mês' },
  { meses: 3, rotulo: '3 meses' },
  { meses: 6, rotulo: '6 meses' },
  { meses: 12, rotulo: '12 meses' },
] as const

/**
 * Seção de análise do Dashboard: um filtro de período, uma vez só, acima de
 * tudo o que ele afeta. Trocar o período mantém o quadro anterior esmaecido
 * até o novo chegar — sem skeleton e sem pulo de layout.
 */
export function PainelDeAnalise() {
  // Estado de interface (qual período olhar), não de servidor.
  const [meses, setMeses] = useState<number>(3)
  const { data, isPending, isError, isPlaceholderData } = useAnalise(meses)

  return (
    <section className="mt-10" aria-labelledby="analise-titulo">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="analise-titulo" className="font-heading text-xl font-semibold">
            Análise do período
          </h2>
          <p className="mt-1 min-h-[1.5rem] text-[15px] text-muted">
            {data && intervaloDoPeriodo(data.periodo.inicio, data.periodo.fim)}
          </p>
        </div>

        {/* Mesmo filtro do Financeiro: ativo em brand, inativo em edge. */}
        <div role="group" aria-label="Período da análise" className="flex flex-wrap gap-3">
          {PERIODOS.map((p) => (
            <button
              key={p.meses}
              type="button"
              aria-pressed={meses === p.meses}
              onClick={() => setMeses(p.meses)}
              className={cn(
                'rounded-card px-5 py-3 text-[15px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand',
                meses === p.meses ? 'bg-brand text-white' : 'bg-edge text-ink hover:bg-edge/70',
              )}
            >
              {p.rotulo}
            </button>
          ))}
        </div>
      </div>

      {isError && (
        <p role="alert" className="mb-6 rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar a análise do período.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {data && (
        <div
          aria-busy={isPlaceholderData}
          className={cn(
            'grid grid-cols-1 gap-6 transition-opacity xl:grid-cols-12',
            isPlaceholderData && 'opacity-60',
          )}
        >
          <ResumoDoPeriodo analise={data} className="xl:col-span-12" />
          {/* Receita só vem para o admin; sem ela, as formas ocupam a linha. */}
          <FormasDePagamento
            formas={data.formas_pagamento}
            className={data.receita ? 'xl:col-span-5' : 'xl:col-span-12'}
          />
          {data.receita && (
            <ReceitaNoTempo
              receita={data.receita}
              granularidade={data.periodo.granularidade}
              className="xl:col-span-7"
            />
          )}
          <HorariosDePico horarios={data.horarios} className="xl:col-span-7" />
          {/* O mapa de calor é bem mais alto que uma lista ranqueada: ao lado
              dele vão duas, empilhadas, e a última estica para as bases
              alinharem — sozinha, "Aulas mais marcadas" sobrava ~300px vazia. */}
          <div className="flex flex-col gap-6 xl:col-span-5">
            <AulasMaisMarcadas servicos={data.servicos} />
            <OrigemDasReservas origens={data.origens} className="flex-1" />
          </div>
          <Comparecimento presenca={data.presenca} className="xl:col-span-12" />
        </div>
      )}
    </section>
  )
}
