import { useState } from 'react'

import { useServicos } from '@/api/servicos'
import { useInstrutores } from '@/api/usuarios'
import {
  useCriarMatricula,
  useEncerrarMatricula,
  useMatriculas,
  useReativarMatricula,
  useSuspenderMatricula,
} from '@/api/matriculas'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import { cn } from '@/lib/cn'
import { data as formatarData, reais } from '@/lib/formato'
import { DIA_LABEL } from '@/types/agenda'
import { STATUS_MATRICULA_LABEL, type Matricula } from '@/types/matricula'
import type { Paciente } from '@/types/paciente'

/** Horas cheias em que o studio pode atender. Só para o formulário. */
const HORAS = Array.from({ length: 15 }, (_, i) => `${String(6 + i).padStart(2, '0')}:00`)
const DIAS_UTEIS = [1, 2, 3, 4, 5, 6]

function erroDe(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : 'Não foi possível concluir a ação.'
}

function CardMatricula({ m, onErro }: { m: Matricula; onErro: (s: string) => void }) {
  const suspender = useSuspenderMatricula()
  const encerrar = useEncerrarMatricula()
  const reativar = useReativarMatricula()

  async function agir(fn: () => Promise<unknown>) {
    try {
      await fn()
    } catch (e) {
      onErro(erroDe(e))
    }
  }

  return (
    <li className="rounded-card border border-edge p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">{m.servico_nome}</p>
          <p className="text-sm text-muted">
            {m.instrutor_nome} · {reais(m.valor_mensal_centavos)}/mês · vence dia{' '}
            {m.dia_vencimento}
          </p>
        </div>
        <span
          className={cn(
            'rounded-full px-3 py-1 text-sm',
            m.status === 'ativa' ? 'bg-badge-confirmado' : 'bg-edge',
          )}
        >
          {STATUS_MATRICULA_LABEL[m.status]}
        </span>
      </div>

      <p className="mt-2 text-[15px]">
        {/* Frequência é derivada da contagem de horários, nunca um campo. */}
        <strong>{m.frequencia_semanal}x por semana:</strong>{' '}
        {m.horarios
          .map((h) => `${DIA_LABEL[h.dia_semana]} ${h.hora_inicio.slice(0, 5)}`)
          .join(' · ')}
      </p>
      <p className="mt-1 text-sm text-muted">
        Desde {formatarData(m.vigencia_inicio)}
        {m.vigencia_fim && ` · até ${formatarData(m.vigencia_fim)}`}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {m.status === 'ativa' && (
          <>
            <Button
              variante="secundario"
              className="px-3 py-2 text-sm"
              onClick={() => agir(() => suspender.mutateAsync({ id: m.id, motivo: 'Suspensa pela recepção' }))}
            >
              Suspender
            </Button>
            <Button
              variante="secundario"
              className="px-3 py-2 text-sm"
              onClick={() => agir(() => encerrar.mutateAsync({ id: m.id, motivo: 'Encerrada pela recepção' }))}
            >
              Encerrar
            </Button>
          </>
        )}
        {m.status === 'suspensa' && (
          <Button
            variante="acento"
            className="px-3 py-2 text-sm"
            onClick={() => agir(() => reativar.mutateAsync(m.id))}
          >
            Reativar
          </Button>
        )}
      </div>
    </li>
  )
}

export function PainelDeMatriculas({ paciente }: { paciente: Paciente }) {
  const [erro, setErro] = useState<string | null>(null)
  const [criando, setCriando] = useState(false)
  const [servicoId, setServicoId] = useState('')
  const [instrutorId, setInstrutorId] = useState('')
  const [valor, setValor] = useState('')
  const [slots, setSlots] = useState<{ dia: number; hora: string }[]>([])

  const { data: matriculas } = useMatriculas(paciente.id)
  const { data: servicos } = useServicos()
  const { data: instrutores } = useInstrutores()
  const criar = useCriarMatricula()

  const mensalidades = servicos?.filter((s) => s.modelo_cobranca === 'mensalidade') ?? []

  function alternarSlot(dia: number, hora: string) {
    setSlots((atual) => {
      const existe = atual.some((s) => s.dia === dia && s.hora === hora)
      return existe
        ? atual.filter((s) => !(s.dia === dia && s.hora === hora))
        : [...atual, { dia, hora }]
    })
  }

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-3">
        {(matriculas ?? []).map((m) => (
          <CardMatricula key={m.id} m={m} onErro={setErro} />
        ))}
      </ul>

      {matriculas && matriculas.length === 0 && !criando && (
        <p className="text-[15px] text-muted">Nenhuma matrícula ainda.</p>
      )}

      {!criando && (
        <Button variante="secundario" onClick={() => setCriando(true)}>
          Nova matrícula
        </Button>
      )}

      {criando && (
        <div className="flex flex-col gap-4 border-t border-edge pt-4">
          <Campo id="mat-servico" label="Serviço" obrigatorio>
            <Select
              id="mat-servico"
              value={servicoId}
              onChange={(e) => setServicoId(e.target.value)}
            >
              <option value="">Selecione…</option>
              {mensalidades.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nome} (turma de {s.capacidade_padrao})
                </option>
              ))}
            </Select>
          </Campo>

          <Campo id="mat-instrutor" label="Instrutor" obrigatorio>
            <Select
              id="mat-instrutor"
              value={instrutorId}
              onChange={(e) => setInstrutorId(e.target.value)}
            >
              <option value="">Selecione…</option>
              {instrutores?.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.nome}
                </option>
              ))}
            </Select>
          </Campo>

          <Campo id="mat-valor" label="Mensalidade (R$)" obrigatorio>
            <Input
              id="mat-valor"
              type="number"
              min={0}
              step="0.01"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </Campo>

          <div>
            <p className="mb-2 text-sm font-medium">
              Horários fixos <span className="text-danger">*</span>
              <span className="ml-2 font-normal text-muted">
                {slots.length > 0 && `${slots.length}x por semana`}
              </span>
            </p>
            <div className="max-h-56 overflow-y-auto rounded-card border border-edge p-2">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="p-1" />
                    {DIAS_UTEIS.map((d) => (
                      <th key={d} className="p-1 font-medium">
                        {DIA_LABEL[d]?.slice(0, 3)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {HORAS.map((h) => (
                    <tr key={h}>
                      <th className="p-1 text-left font-normal text-muted">{h}</th>
                      {DIAS_UTEIS.map((d) => {
                        const marcado = slots.some((s) => s.dia === d && s.hora === h)
                        return (
                          <td key={d} className="p-1 text-center">
                            <button
                              type="button"
                              aria-label={`${DIA_LABEL[d]} ${h}`}
                              aria-pressed={marcado}
                              onClick={() => alternarSlot(d, h)}
                              className={cn(
                                'h-6 w-full rounded transition-colors',
                                marcado ? 'bg-brand' : 'bg-subtle hover:bg-edge',
                              )}
                            />
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {erro && <Aviso>{erro}</Aviso>}

          <div className="flex gap-3">
            <Button
              className="flex-1"
              disabled={!servicoId || !instrutorId || !valor || slots.length === 0}
              onClick={async () => {
                setErro(null)
                try {
                  await criar.mutateAsync({
                    patient_id: paciente.id,
                    service_id: Number(servicoId),
                    professional_id: Number(instrutorId),
                    vigencia_inicio: new Date().toISOString().slice(0, 10),
                    valor_mensal_centavos: Math.round(Number(valor) * 100),
                    horarios: slots.map((s) => ({
                      dia_semana: s.dia,
                      hora_inicio: `${s.hora}:00`,
                    })),
                  })
                  setCriando(false)
                  setSlots([])
                  setValor('')
                } catch (e) {
                  setErro(erroDe(e))
                }
              }}
            >
              Matricular
            </Button>
            <Button
              variante="secundario"
              className="flex-1"
              onClick={() => {
                setCriando(false)
                setErro(null)
              }}
            >
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {erro && !criando && <Aviso>{erro}</Aviso>}
    </div>
  )
}
