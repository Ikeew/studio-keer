import { Activity, CalendarDays, TrendingUp, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { useIndicadores } from '@/api/dashboard'
import { AvisoDeGrade } from '@/features/agenda/AvisoDeGrade'
import { PageHeader } from '@/components/ui/PageHeader'
import { cn } from '@/lib/cn'
import { STATUS_LABEL } from '@/types/agenda'

function Kpi({
  icone: Icone,
  cor,
  valor,
  rotulo,
  detalhe,
  titulo,
}: {
  icone: LucideIcon
  cor: string
  valor: string
  rotulo: string
  detalhe?: string
  titulo?: string
}) {
  return (
    <div className="rounded-card border border-edge bg-surface p-6 shadow-card" title={titulo}>
      <span
        className="flex h-12 w-12 items-center justify-center rounded-card text-white"
        style={{ backgroundColor: cor }}
      >
        <Icone size={24} />
      </span>
      <p className="mt-4 font-heading text-4xl font-semibold">{valor}</p>
      <p className="mt-1 text-[15px] text-muted">{rotulo}</p>
      {detalhe && <p className="mt-1 text-sm text-muted">{detalhe}</p>}
    </div>
  )
}

export function Dashboard() {
  const { data, isPending, isError } = useIndicadores()

  return (
    <>
      <PageHeader title="Dashboard" subtitle="Visão geral do seu estúdio" />

      <AvisoDeGrade />

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar os indicadores.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
            <Kpi
              icone={CalendarDays}
              cor="#06B6D4"
              valor={String(data.agendamentos_hoje)}
              rotulo="Agendamentos Hoje"
            />
            <Kpi
              icone={Users}
              cor="#7C2D8E"
              valor={String(data.pacientes_ativos)}
              rotulo="Pacientes Ativos"
            />
            <Kpi
              icone={Activity}
              cor="#06B6D4"
              valor={String(data.sessoes_no_mes)}
              rotulo="Sessões no Mês"
            />
            <Kpi
              icone={TrendingUp}
              cor="#A855F7"
              valor={`${data.ocupacao.percentual}%`}
              rotulo="Taxa de Ocupação"
              // Numerador e denominador na tela: percentual sozinho não é
              // auditável, e este é o número que a banca vai questionar.
              detalhe={`${data.ocupacao.reservas_ativas} de ${data.ocupacao.capacidade_ofertada} lugares no mês`}
              titulo={data.ocupacao.formula}
            />
          </div>

          <section className="mt-8 rounded-card border border-edge bg-surface p-6 shadow-card">
            <h2 className="font-heading text-xl font-semibold">Próximos Agendamentos</h2>

            {data.proximos.length === 0 ? (
              <p className="mt-4 text-[15px] text-muted">
                Nenhum agendamento para hoje.
              </p>
            ) : (
              <ul className="mt-4 flex flex-col gap-3">
                {data.proximos.map((p) => (
                  <li
                    key={p.booking_id}
                    className="flex flex-wrap items-center gap-4 rounded-card bg-subtle p-3"
                  >
                    <span className="rounded-card bg-accent px-3 py-2 text-sm font-medium text-white">
                      {p.hora}
                    </span>
                    <span>
                      <span className="block font-medium">{p.paciente_nome}</span>
                      <span className="block text-sm text-muted">
                        {p.servico_nome} · {p.instrutor_nome}
                      </span>
                    </span>
                    <span
                      className={cn(
                        'ml-auto rounded-full px-3 py-1 text-sm',
                        p.status === 'confirmada' && 'bg-badge-confirmado',
                        p.status === 'presente' && 'bg-badge-pago',
                        p.status === 'falta' && 'bg-badge-alerta',
                        p.status === 'agendada' && 'bg-badge-aguardando',
                      )}
                    >
                      {STATUS_LABEL[p.status]}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  )
}
