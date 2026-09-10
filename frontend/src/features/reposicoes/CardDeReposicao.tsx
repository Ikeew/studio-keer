import { AlertTriangle, CalendarClock, Phone } from 'lucide-react'
import { useState } from 'react'

import { useCriarReserva, useSessoesComVaga } from '@/api/agenda'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { data as formatarData, telefone as formatarTel } from '@/lib/formato'
import { DIA_LABEL } from '@/types/agenda'
import type { FaltaPendente } from '@/types/matricula'

type Props = { falta: FaltaPendente }

/**
 * Uma falta pendente, com os horários que podem recebê-la.
 *
 * Mostra tudo que a recepção precisa para resolver sem sair da tela: quem é,
 * de quando, até quando dá para repor, o telefone para ligar, e os horários
 * com vaga REAL na janela.
 */
export function CardDeReposicao({ falta }: Props) {
  const [aberto, setAberto] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [feito, setFeito] = useState(false)

  const criar = useCriarReserva()
  const { data: vagas, isPending } = useSessoesComVaga({
    de: falta.procurar_de,
    ate: falta.procurar_ate,
    serviceId: falta.service_id,
    excluirPacienteId: falta.patient_id,
    habilitado: aberto,
  })

  const urgente = falta.dias_restantes !== null && falta.dias_restantes <= 7
  const vencida = falta.dias_restantes !== null && falta.dias_restantes < 0

  return (
    <article
      className={cn(
        'rounded-card border bg-surface p-5 shadow-card',
        urgente ? 'border-danger/40' : 'border-edge',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-heading text-lg font-semibold">{falta.paciente_nome}</h3>
          <p className="mt-1 text-[15px] text-muted">
            Faltou em {formatarData(falta.faltou_em.slice(0, 10))} · {falta.servico_nome}
          </p>
          {falta.motivo && (
            <p className="mt-1 text-sm text-muted">Motivo: {falta.motivo}</p>
          )}
        </div>

        <span
          className={cn(
            'flex items-center gap-2 rounded-full px-3 py-1 text-sm',
            vencida
              ? 'bg-badge-alerta text-ink'
              : urgente
                ? 'bg-badge-alerta text-ink'
                : 'bg-badge-confirmado text-ink',
          )}
        >
          {urgente && <AlertTriangle size={14} />}
          {falta.repor_ate === null
            ? 'Sem prazo'
            : vencida
              ? `Venceu em ${formatarData(falta.repor_ate)}`
              : `Repor até ${formatarData(falta.repor_ate)} · ${falta.dias_restantes} dia${
                  falta.dias_restantes === 1 ? '' : 's'
                }`}
        </span>
      </div>

      {falta.paciente_telefone && (
        <p className="mt-3 flex items-center gap-2 text-[15px] text-muted">
          <Phone size={16} /> {formatarTel(falta.paciente_telefone)}
        </p>
      )}

      {feito && <Aviso tipo="info">Reposição agendada.</Aviso>}

      {!feito && !aberto && (
        <Button variante="secundario" className="mt-4" onClick={() => setAberto(true)}>
          <CalendarClock size={18} /> Ver horários com vaga
        </Button>
      )}

      {!feito && aberto && (
        <div className="mt-4 border-t border-edge pt-4">
          {isPending && <p className="text-[15px] text-muted">Procurando vagas…</p>}

          {vagas && vagas.length === 0 && (
            // Sem vaga o sistema diz isso explicitamente, e não oferece
            // caminho para forçar. É a regra central do projeto.
            <Aviso>
              Não há nenhum horário de {falta.servico_nome} com vaga até{' '}
              {formatarData(falta.procurar_ate)}. Para abrir espaço, cancele uma
              reserva existente na agenda — cancelamento libera o lugar na hora.
            </Aviso>
          )}

          {vagas && vagas.length > 0 && (
            <ul className="flex max-h-64 flex-col gap-2 overflow-y-auto">
              {vagas.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 rounded-card border border-edge p-3 text-left transition-colors hover:bg-subtle"
                    onClick={async () => {
                      setErro(null)
                      try {
                        await criar.mutateAsync({
                          session_id: s.id,
                          patient_id: falta.patient_id,
                          origem: 'reposicao',
                          substitui_booking_id: falta.booking_id,
                        })
                        setFeito(true)
                      } catch (e) {
                        const d = (e as { response?: { data?: { detail?: unknown } } })
                          ?.response?.data?.detail
                        setErro(
                          typeof d === 'string' ? d : 'Não foi possível agendar.',
                        )
                      }
                    }}
                  >
                    <span>
                      <span className="block font-medium">
                        {DIA_LABEL[new Date(`${s.dia}T12:00:00`).getDay()]} ·{' '}
                        {formatarData(s.dia)} às {s.hora}
                      </span>
                      <span className="block text-sm text-muted">
                        {s.servico_nome} · {s.instrutor_nome}
                      </span>
                    </span>
                    <span className="shrink-0 rounded-full bg-badge-confirmado px-3 py-1 text-sm">
                      {s.vagas} vaga{s.vagas === 1 ? '' : 's'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {erro && <Aviso>{erro}</Aviso>}
        </div>
      )}
    </article>
  )
}
