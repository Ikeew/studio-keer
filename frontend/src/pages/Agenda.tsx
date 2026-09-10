import { ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { useMemo, useState } from 'react'

import { useGradeSemanal } from '@/api/agenda'
import { useAuth } from '@/auth/useAuth'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { CelulaDaGrade } from '@/features/agenda/CelulaDaGrade'
import { Legenda } from '@/features/agenda/Legenda'
import { NovaTurmaForm } from '@/features/agenda/NovaTurmaForm'
import { PainelDaSessao } from '@/features/agenda/PainelDaSessao'
import { PainelRemarcar } from '@/features/agenda/PainelRemarcar'
import { useInstrutores } from '@/api/usuarios'
import { data as formatarData } from '@/lib/formato'
import { DIA_LABEL, type SessaoNaGrade } from '@/types/agenda'

function segundaDe(d: Date): string {
  const copia = new Date(d)
  const diff = (copia.getDay() + 6) % 7
  copia.setDate(copia.getDate() - diff)
  return copia.toISOString().slice(0, 10)
}

function somarDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T12:00:00`)
  d.setDate(d.getDate() + dias)
  return d.toISOString().slice(0, 10)
}

export function Agenda() {
  const { usuario } = useAuth()
  const podeEscrever = usuario?.papel === 'admin' || usuario?.papel === 'recepcao'

  const [referencia, setReferencia] = useState(() => segundaDe(new Date()))
  const [sessaoAberta, setSessaoAberta] = useState<SessaoNaGrade | null>(null)
  const [criandoTurma, setCriandoTurma] = useState(false)
  const [remarcando, setRemarcando] = useState<{
    reservaId: number
    nome: string
    pacienteId: number
  } | null>(null)

  const { data: grade, isPending, isError } = useGradeSemanal(referencia)
  // Só a recepção e a proprietária criam turma; o instrutor não deve
  // sequer disparar a requisição, que ele receberia como 403.
  const { data: instrutores } = useInstrutores(podeEscrever)

  // Todas as horas que aparecem em algum dia da semana. Vêm da API já sem a
  // pausa e sem o que está fora da janela — a tela não filtra nada.
  const horas = useMemo(() => {
    const todas = new Set<string>()
    grade?.dias.forEach((d) => d.horas.forEach((h) => todas.add(h)))
    return [...todas].sort()
  }, [grade])

  const diasAbertos = grade?.dias.filter((d) => d.aberto) ?? []

  const sessoesPor = useMemo(() => {
    const mapa = new Map<string, SessaoNaGrade[]>()
    grade?.sessoes.forEach((s) => {
      const chave = `${s.dia}|${s.hora}`
      mapa.set(chave, [...(mapa.get(chave) ?? []), s])
    })
    return mapa
  }, [grade])

  // Mantém o painel sincronizado depois de uma ação (marcar presença, etc).
  const sessaoAtual = sessaoAberta
    ? (grade?.sessoes.find((s) => s.id === sessaoAberta.id) ?? sessaoAberta)
    : null

  return (
    <>
      <PageHeader
        title="Agendamentos"
        subtitle="Visualização semanal"
        action={
          <div className="flex items-center gap-3">
            {podeEscrever && (
              <Button onClick={() => setCriandoTurma(true)}>
                <Plus size={20} /> Nova Turma
              </Button>
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Semana anterior"
                onClick={() => setReferencia((r) => somarDias(r, -7))}
                className="rounded-card p-2 transition-colors hover:bg-edge"
              >
                <ChevronLeft size={22} />
              </button>
              <span className="min-w-[190px] text-center text-[15px] font-medium">
                {grade
                  ? `${formatarData(grade.inicio)} – ${formatarData(grade.fim)}`
                  : 'Carregando…'}
              </span>
              <button
                type="button"
                aria-label="Próxima semana"
                onClick={() => setReferencia((r) => somarDias(r, 7))}
                className="rounded-card p-2 transition-colors hover:bg-edge"
              >
                <ChevronRight size={22} />
              </button>
            </div>
          </div>
        }
      />

      <Legenda sessoes={grade?.sessoes ?? []} />

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar a agenda.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {grade && (
        <div className="overflow-x-auto rounded-card border border-edge bg-surface">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-subtle">
                <th className="w-24 border border-edge p-3 text-sm font-medium text-muted">
                  Horário
                </th>
                {diasAbertos.map((d) => (
                  <th key={d.data} className="border border-edge p-3">
                    <span className="block font-heading text-[15px] font-semibold">
                      {DIA_LABEL[d.dia_semana]}
                    </span>
                    <span className="block text-sm font-normal text-muted">
                      {formatarData(d.data)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {horas.map((hora) => (
                <tr key={hora}>
                  <th className="border border-edge bg-subtle p-2 align-top">
                    <span className="rounded-full bg-accent px-3 py-1 text-sm text-white">
                      {hora}
                    </span>
                  </th>
                  {diasAbertos.map((d) => (
                    <CelulaDaGrade
                      key={`${d.data}|${hora}`}
                      aberto={d.horas.includes(hora)}
                      sessoes={sessoesPor.get(`${d.data}|${hora}`) ?? []}
                      onAbrirSessao={setSessaoAberta}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {grade && horas.length > 0 && (
        <p className="mt-4 text-sm text-muted">
          A pausa das {grade.dias.find((d) => d.pausa_inicio)?.pausa_inicio?.slice(0, 5)} às{' '}
          {grade.dias.find((d) => d.pausa_fim)?.pausa_fim?.slice(0, 5)} não aparece na
          grade — o studio não atende nesse intervalo.
        </p>
      )}

      <Modal
        aberto={sessaoAtual !== null}
        titulo={sessaoAtual ? `Turma das ${sessaoAtual.hora}` : ''}
        onFechar={() => setSessaoAberta(null)}
      >
        {sessaoAtual && podeEscrever && (
          <PainelDaSessao
            sessao={sessaoAtual}
            onRemarcar={(reservaId, nome) => {
              const reserva = sessaoAtual.reservas.find((r) => r.id === reservaId)
              setSessaoAberta(null)
              if (reserva) {
                setRemarcando({ reservaId, nome, pacienteId: reserva.patient_id })
              }
            }}
          />
        )}
        {sessaoAtual && !podeEscrever && (
          <div>
            <p className="text-[15px]">
              <strong>{sessaoAtual.servico_nome}</strong> · {sessaoAtual.instrutor_nome}
            </p>
            <ul className="mt-3 flex flex-col gap-1">
              {sessaoAtual.reservas.map((r) => (
                <li key={r.id} className="text-[15px]">
                  {r.paciente_nome}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Modal>

      <Modal
        aberto={remarcando !== null}
        titulo="Remarcar"
        onFechar={() => setRemarcando(null)}
      >
        {remarcando && grade && (
          <PainelRemarcar
            reservaId={remarcando.reservaId}
            pacienteNome={remarcando.nome}
            pacienteId={remarcando.pacienteId}
            de={grade.inicio}
            ate={grade.fim}
            onPronto={() => setRemarcando(null)}
          />
        )}
      </Modal>

      <Modal
        aberto={criandoTurma}
        titulo="Nova Turma"
        onFechar={() => setCriandoTurma(false)}
      >
        {grade && (
          <NovaTurmaForm
            dias={grade.dias}
            instrutores={instrutores ?? []}
            onPronto={() => setCriandoTurma(false)}
          />
        )}
      </Modal>
    </>
  )
}
