import { AlertTriangle, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { useGerarGrade, useSaudeDaGrade } from '@/api/matriculas'
import { useAuth } from '@/auth/useAuth'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { data as formatarData } from '@/lib/formato'

/**
 * Avisa quando a grade recorrente está acabando.
 *
 * A geração é manual (não há job agendado nesta entrega), e o modo de falha
 * é SILENCIOSO: a grade esvazia sem erro nenhum, a busca por vaga para de
 * achar horário, e a recepção volta a encaixar de cabeça — que é a dor que o
 * sistema existe para resolver.
 *
 * Não aparece quando está tudo bem, nem quando não há matrícula ativa (não
 * haveria grade a manter, e o aviso seria só ruído).
 */
export function AvisoDeGrade() {
  const { usuario } = useAuth()
  const podeGerar = usuario?.papel === 'admin' || usuario?.papel === 'recepcao'
  const { data: saude } = useSaudeDaGrade()
  const gerar = useGerarGrade()
  const [resultado, setResultado] = useState<string | null>(null)

  if (!saude || !saude.precisa_atualizar) return null

  return (
    <div
      role="alert"
      className={cn(
        'mb-6 flex flex-wrap items-center justify-between gap-4 rounded-card border p-4',
        saude.vencida ? 'border-danger bg-badge-alerta' : 'border-edge bg-subtle',
      )}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          size={22}
          className={saude.vencida ? 'mt-0.5 text-danger' : 'mt-0.5 text-muted'}
        />
        <div>
          <p className="font-medium">
            {saude.vencida
              ? 'A grade de horários fixos acabou.'
              : `A grade de horários fixos termina em ${formatarData(
                  saude.materializado_ate ?? '',
                )}.`}
          </p>
          <p className="mt-1 text-[15px] text-muted">
            {saude.vencida
              ? `Há ${saude.matriculas_ativas} matrícula${
                  saude.matriculas_ativas === 1 ? '' : 's'
                } ativa${saude.matriculas_ativas === 1 ? '' : 's'} sem aulas marcadas. ` +
                'Enquanto isso, não há horário para oferecer em reposições.'
              : `Restam ${saude.semanas_restantes} semana${
                  saude.semanas_restantes === 1 ? '' : 's'
                }. Abaixo de ${saude.semanas_minimas}, a busca por vaga para reposição ` +
                'começa a não achar horários que deveriam existir.'}
          </p>
          {resultado && <p className="mt-1 text-[15px]">{resultado}</p>}
        </div>
      </div>

      {podeGerar && (
        <Button
          disabled={gerar.isPending}
          onClick={async () => {
            const r = await gerar.mutateAsync(undefined)
            setResultado(
              `${r.reservas_criadas} reservas criadas` +
                (r.sem_vaga.length ? ` · ${r.sem_vaga.length} sem vaga` : ''),
            )
          }}
        >
          <RefreshCw size={18} />
          {gerar.isPending ? 'Atualizando…' : 'Atualizar grade agora'}
        </Button>
      )}
    </div>
  )
}
