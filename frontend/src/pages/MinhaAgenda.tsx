import { Clock } from 'lucide-react'

import { useMinhaAgenda } from '@/api/dashboard'
import { PageHeader } from '@/components/ui/PageHeader'
import { usePageTitle } from '@/hooks/usePageTitle'
import { cn } from '@/lib/cn'
import { STATUS_LABEL } from '@/types/agenda'

/**
 * Agenda de hoje do instrutor. SOMENTE LEITURA.
 *
 * Quem registra presença e falta é a recepção (CLAUDE.md). Esta tela não tem
 * nenhuma ação — dar escrita ao instrutor é evolução futura, e o backend
 * recusaria de qualquer forma.
 */
export function MinhaAgenda() {
  usePageTitle('Minha Agenda')
  const { data: aulas, isPending, isError } = useMinhaAgenda()

  const hoje = new Date().toLocaleDateString('pt-BR', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
  })

  return (
    <>
      <PageHeader title="Minha Agenda" subtitle={`Aulas de hoje · ${hoje}`} />

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar a sua agenda.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {aulas && aulas.length === 0 && (
        <div className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
          <Clock size={32} className="mx-auto text-muted" />
          <p className="mt-3 text-[15px] text-muted">
            Nenhuma aula marcada para hoje.
          </p>
        </div>
      )}

      {aulas && aulas.length > 0 && (
        <>
          <p className="mb-4 text-[15px] text-muted">
            {aulas.length} aluno{aulas.length === 1 ? '' : 's'} hoje
          </p>
          <ul className="flex flex-col gap-3">
            {aulas.map((a) => (
              <li
                key={a.booking_id}
                className="flex flex-wrap items-center gap-4 rounded-card border border-edge bg-surface p-4 shadow-card"
              >
                <span className="rounded-card bg-accent px-4 py-2 font-medium text-white">
                  {a.hora}
                </span>
                <span>
                  <span className="block font-medium">{a.paciente_nome}</span>
                  <span className="block text-sm text-muted">{a.servico_nome}</span>
                </span>
                <span
                  className={cn(
                    'ml-auto rounded-full px-3 py-1 text-sm',
                    a.status === 'confirmada' && 'bg-badge-confirmado',
                    a.status === 'presente' && 'bg-badge-pago',
                    a.status === 'falta' && 'bg-badge-alerta',
                    a.status === 'agendada' && 'bg-badge-aguardando',
                  )}
                >
                  {STATUS_LABEL[a.status]}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-6 rounded-card bg-subtle px-4 py-3 text-sm text-muted">
            Esta tela é somente leitura. Presença e falta são registradas pela
            recepção.
          </p>
        </>
      )}
    </>
  )
}
