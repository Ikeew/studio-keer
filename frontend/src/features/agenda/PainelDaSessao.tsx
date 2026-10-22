import { useState } from 'react'

import {
  useCancelarReserva,
  useConfirmarReserva,
  useCriarReserva,
  useFalta,
  useLimparPresenca,
  usePresenca,
} from '@/api/agenda'
import { usePacientes } from '@/api/pacientes'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import { cn } from '@/lib/cn'
import { dataHora } from '@/lib/formato'
import { ORIGEM_LABEL, STATUS_LABEL, type SessaoNaGrade } from '@/types/agenda'

type Props = {
  sessao: SessaoNaGrade
  onRemarcar: (reservaId: number, pacienteNome: string) => void
}

function erroDe(e: unknown): string {
  const detalhe = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detalhe === 'string' ? detalhe : 'Não foi possível concluir a ação.'
}

export function PainelDaSessao({ sessao, onRemarcar }: Props) {
  const [erro, setErro] = useState<string | null>(null)
  const [pacienteId, setPacienteId] = useState('')
  const [motivoFalta, setMotivoFalta] = useState<Record<number, string>>({})

  const { data: pagina } = usePacientes({ tamanho: 100 })
  const criar = useCriarReserva()
  const cancelar = useCancelarReserva()
  const confirmar = useConfirmarReserva()
  const presenca = usePresenca()
  const falta = useFalta()
  const limpar = useLimparPresenca()

  const jaNaTurma = new Set(sessao.reservas.map((r) => r.patient_id))
  const disponiveis = (pagina?.itens ?? []).filter((p) => !jaNaTurma.has(p.id))

  async function agir(fn: () => Promise<unknown>) {
    setErro(null)
    try {
      await fn()
    } catch (e) {
      setErro(erroDe(e))
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-card bg-subtle p-4">
        <p className="text-[15px]">
          <strong>{sessao.servico_nome}</strong> · {sessao.instrutor_nome}
        </p>
        <p className="mt-1 text-sm text-muted">
          {sessao.hora} · {sessao.ocupadas} de {sessao.capacidade} lugares ocupados
        </p>
      </div>

      <div>
        <h3 className="mb-2 font-heading text-lg font-semibold">Pacientes na turma</h3>
        {sessao.reservas.length === 0 && (
          <p className="text-[15px] text-muted">Ninguém marcado ainda.</p>
        )}
        <ul className="flex flex-col gap-3">
          {sessao.reservas.map((r) => (
            <li key={r.id} className="rounded-card border border-edge p-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{r.paciente_nome}</span>
                <span
                  className={cn(
                    'rounded-full px-3 py-1 text-sm',
                    r.status === 'falta' ? 'bg-badge-alerta' : 'bg-badge-confirmado',
                  )}
                >
                  {STATUS_LABEL[r.status]}
                  {r.status === 'falta' && r.justificada && ' · justificada'}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">
                {ORIGEM_LABEL[r.origem]}
                {r.presenca_por && r.presenca_em && (
                  <> · registrado por {r.presenca_por} em {dataHora(r.presenca_em)}</>
                )}
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {r.status === 'agendada' && (
                  <Button
                    variante="secundario"
                    className="px-3 py-2 text-sm"
                    onClick={() => agir(() => confirmar.mutateAsync(r.id))}
                  >
                    Confirmar
                  </Button>
                )}
                {r.status !== 'presente' && r.status !== 'falta' && (
                  <>
                    <Button
                      variante="acento"
                      className="px-3 py-2 text-sm"
                      onClick={() => agir(() => presenca.mutateAsync(r.id))}
                    >
                      Presente
                    </Button>
                    <Button
                      variante="secundario"
                      className="px-3 py-2 text-sm"
                      onClick={() =>
                        agir(() =>
                          falta.mutateAsync({
                            id: r.id,
                            justificada: false,
                            motivo: motivoFalta[r.id],
                          }),
                        )
                      }
                    >
                      Faltou
                    </Button>
                    <Button
                      variante="secundario"
                      className="px-3 py-2 text-sm"
                      onClick={() =>
                        agir(() =>
                          falta.mutateAsync({
                            id: r.id,
                            justificada: true,
                            motivo: motivoFalta[r.id] || 'Justificada pela recepção',
                          }),
                        )
                      }
                    >
                      Faltou (justificada)
                    </Button>
                    <Button
                      variante="secundario"
                      className="px-3 py-2 text-sm"
                      onClick={() => onRemarcar(r.id, r.paciente_nome)}
                    >
                      Remarcar
                    </Button>
                    {/* Avisar dá direito a repor; cancelar é só desfazer a reserva. */}
                    <Button
                      variante="secundario"
                      className="px-3 py-2 text-sm"
                      title="Libera a vaga e entra nas Reposições Pendentes"
                      onClick={() =>
                        agir(() =>
                          cancelar.mutateAsync({
                            id: r.id,
                            motivo: motivoFalta[r.id] || 'Avisou que não vem',
                            comAviso: true,
                          }),
                        )
                      }
                    >
                      Avisou que não vem
                    </Button>
                    <Button
                      variante="secundario"
                      className="px-3 py-2 text-sm"
                      title="Desfaz a reserva sem gerar reposição"
                      onClick={() =>
                        agir(() =>
                          cancelar.mutateAsync({ id: r.id, motivo: 'Reserva cancelada' }),
                        )
                      }
                    >
                      Cancelar reserva
                    </Button>
                  </>
                )}
                {/* O atestado costuma chegar depois da aula. Sem isto, a falta
                    marcada como comum nunca entraria nas reposições. */}
                {r.status === 'falta' && !r.justificada && (
                  <Button
                    variante="secundario"
                    className="px-3 py-2 text-sm"
                    onClick={() =>
                      agir(() =>
                        falta.mutateAsync({
                          id: r.id,
                          justificada: true,
                          motivo: motivoFalta[r.id] || 'Justificada pela recepção',
                        }),
                      )
                    }
                  >
                    Justificar falta
                  </Button>
                )}
                {/* Correção de registro errado. Se a falta já foi reposta, o
                    backend recusa e a mensagem diz o que fazer. */}
                {r.status === 'presente' && (
                  <Button
                    variante="secundario"
                    className="px-3 py-2 text-sm"
                    onClick={() =>
                      agir(() => falta.mutateAsync({ id: r.id, justificada: false }))
                    }
                  >
                    Corrigir: faltou
                  </Button>
                )}
                {r.status === 'falta' && (
                  <Button
                    variante="secundario"
                    className="px-3 py-2 text-sm"
                    onClick={() => agir(() => presenca.mutateAsync(r.id))}
                  >
                    Corrigir: presente
                  </Button>
                )}
                {(r.status === 'presente' || r.status === 'falta') && (
                  <Button
                    variante="secundario"
                    className="px-3 py-2 text-sm"
                    title="Volta a reserva para sem registro de presença"
                    onClick={() => agir(() => limpar.mutateAsync(r.id))}
                  >
                    Limpar registro
                  </Button>
                )}
              </div>

              {r.status !== 'presente' && !(r.status === 'falta' && r.justificada) && (
                <Input
                  placeholder="Motivo (opcional)"
                  className="mt-2 py-2 text-sm"
                  value={motivoFalta[r.id] ?? ''}
                  onChange={(e) =>
                    setMotivoFalta((m) => ({ ...m, [r.id]: e.target.value }))
                  }
                />
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t border-edge pt-5">
        <h3 className="mb-2 font-heading text-lg font-semibold">Adicionar paciente</h3>
        {sessao.lotada ? (
          // A tela diz que não há vaga ANTES de a recepção oferecer ao
          // paciente, e não existe botão para forçar.
          <Aviso>
            Turma cheia ({sessao.ocupadas} de {sessao.capacidade}). Para abrir uma vaga,
            cancele uma reserva existente — cancelamento libera o lugar na hora.
          </Aviso>
        ) : (
          <div className="flex gap-3">
            <Campo id="paciente" label="" >
              <Select
                id="paciente"
                value={pacienteId}
                onChange={(e) => setPacienteId(e.target.value)}
              >
                <option value="">Selecione…</option>
                {disponiveis.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome_exibicao}
                  </option>
                ))}
              </Select>
            </Campo>
            <Button
              disabled={!pacienteId}
              className="self-start"
              onClick={() =>
                agir(async () => {
                  await criar.mutateAsync({
                    session_id: sessao.id,
                    patient_id: Number(pacienteId),
                    origem: 'avulsa',
                  })
                  setPacienteId('')
                })
              }
            >
              Agendar
            </Button>
          </div>
        )}
      </div>

      {erro && <Aviso>{erro}</Aviso>}
    </div>
  )
}
