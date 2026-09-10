import { CalendarCheck, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { useGerarGrade } from '@/api/matriculas'
import { useReposicoesPendentes } from '@/api/matriculas'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { PageHeader } from '@/components/ui/PageHeader'
import { CardDeReposicao } from '@/features/reposicoes/CardDeReposicao'

/**
 * Reposições pendentes.
 *
 * Tela de destaque, e não consulta secundária: é a única coisa que o sistema
 * faz que a proprietária hoje não consegue fazer de jeito nenhum — só
 * lembrar de cabeça.
 */
export function Reposicoes() {
  const [incluirVencidas, setIncluirVencidas] = useState(false)
  const { data: faltas, isPending, isError } = useReposicoesPendentes(incluirVencidas)
  const gerar = useGerarGrade()
  const [resultado, setResultado] = useState<string | null>(null)

  const urgentes =
    faltas?.filter((f) => f.dias_restantes !== null && f.dias_restantes <= 7).length ?? 0

  return (
    <>
      <PageHeader
        title="Reposições Pendentes"
        subtitle="Faltas que ainda dão direito a repor"
        action={
          <Button
            variante="secundario"
            disabled={gerar.isPending}
            onClick={async () => {
              const r = await gerar.mutateAsync(undefined)
              setResultado(
                `${r.reservas_criadas} reservas criadas, ` +
                  `${r.reservas_ja_existentes} já existiam` +
                  (r.sem_vaga.length ? ` · ${r.sem_vaga.length} sem vaga` : ''),
              )
            }}
          >
            <RefreshCw size={18} />
            {gerar.isPending ? 'Gerando…' : 'Atualizar grade'}
          </Button>
        }
      />

      {resultado && <Aviso tipo="info">{resultado}</Aviso>}

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar as reposições.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {faltas && (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-4">
            <span className="rounded-card bg-surface px-4 py-3 text-[15px] shadow-card">
              <strong className="text-2xl">{faltas.length}</strong> pendente
              {faltas.length === 1 ? '' : 's'}
            </span>
            {urgentes > 0 && (
              <span className="rounded-card bg-badge-alerta px-4 py-3 text-[15px]">
                <strong className="text-2xl">{urgentes}</strong> vence
                {urgentes === 1 ? '' : 'm'} em até 7 dias
              </span>
            )}
            <label className="ml-auto flex items-center gap-2 text-[15px]">
              <input
                type="checkbox"
                checked={incluirVencidas}
                onChange={(e) => setIncluirVencidas(e.target.checked)}
                className="h-4 w-4 accent-brand"
              />
              Mostrar prazos vencidos
            </label>
          </div>

          {faltas.length === 0 ? (
            <div className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
              <CalendarCheck size={32} className="mx-auto text-muted" />
              <p className="mt-3 text-[15px] text-muted">
                Nenhuma reposição pendente. Toda falta justificada já foi remarcada.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              {faltas.map((f) => (
                <CardDeReposicao key={f.booking_id} falta={f} />
              ))}
            </div>
          )}
        </>
      )}
    </>
  )
}
