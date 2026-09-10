import { useState } from 'react'

import { useRemarcar, useSessoesComVaga } from '@/api/agenda'
import { Aviso } from '@/components/ui/Aviso'
import { data as formatarData } from '@/lib/formato'
import { DIA_LABEL } from '@/types/agenda'

type Props = {
  reservaId: number
  pacienteNome: string
  pacienteId: number
  de: string
  ate: string
  onPronto: () => void
}

/**
 * Escolha do novo horário para remarcação ou reposição.
 *
 * Mostra SOMENTE turmas com vaga real, consultadas antes de a recepção
 * oferecer o horário ao paciente. Quando não há nenhuma, diz isso
 * explicitamente — não existe caminho para forçar.
 */
export function PainelRemarcar({
  reservaId,
  pacienteNome,
  pacienteId,
  de,
  ate,
  onPronto,
}: Props) {
  const [erro, setErro] = useState<string | null>(null)
  const remarcar = useRemarcar()
  const { data: vagas, isPending } = useSessoesComVaga({
    de,
    ate,
    excluirPacienteId: pacienteId,
  })

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[15px]">
        Novo horário para <strong>{pacienteNome}</strong>:
      </p>

      {isPending && <p className="text-muted">Procurando horários com vaga…</p>}

      {vagas && vagas.length === 0 && (
        <Aviso>
          Não há nenhuma turma com vaga nesta semana. Avance a semana na agenda, ou
          libere um lugar cancelando uma reserva existente.
        </Aviso>
      )}

      {vagas && vagas.length > 0 && (
        <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {vagas.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 rounded-card border border-edge p-3 text-left transition-colors hover:bg-subtle"
                onClick={async () => {
                  setErro(null)
                  try {
                    await remarcar.mutateAsync({
                      id: reservaId,
                      nova_session_id: s.id,
                    })
                    onPronto()
                  } catch (e) {
                    const d = (e as { response?: { data?: { detail?: unknown } } })?.response
                      ?.data?.detail
                    setErro(typeof d === 'string' ? d : 'Não foi possível remarcar.')
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
  )
}
