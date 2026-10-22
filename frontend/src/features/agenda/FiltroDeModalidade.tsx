import { Check } from 'lucide-react'

import { useModalidades } from '@/api/agenda'
import { cn } from '@/lib/cn'

type Props = {
  /** Ids marcados. Vazio = todas as modalidades. */
  selecionadas: number[]
  onMudar: (ids: number[]) => void
}

/**
 * Filtro de modalidade da agenda, com seleção múltipla.
 *
 * Nenhuma marcada é o mesmo que todas: é o estado de quem abre a agenda pela
 * primeira vez, e não pode mostrar uma grade vazia.
 */
export function FiltroDeModalidade({ selecionadas, onMudar }: Props) {
  const { data: modalidades } = useModalidades()
  if (!modalidades || modalidades.length < 2) return null

  const marcadas = new Set(selecionadas)
  const alternar = (id: number) =>
    onMudar(marcadas.has(id) ? selecionadas.filter((s) => s !== id) : [...selecionadas, id])

  return (
    <div role="group" aria-label="Filtrar por modalidade" className="mb-4 flex flex-wrap gap-2">
      <button
        type="button"
        aria-pressed={selecionadas.length === 0}
        onClick={() => onMudar([])}
        className={cn(
          'rounded-full border px-4 py-2 text-[15px] transition-colors',
          selecionadas.length === 0
            ? 'border-brand bg-brand text-white'
            : 'border-edge bg-surface hover:bg-subtle',
        )}
      >
        Todas
      </button>
      {modalidades.map((m) => {
        const ativa = marcadas.has(m.id)
        return (
          <button
            key={m.id}
            type="button"
            aria-pressed={ativa}
            onClick={() => alternar(m.id)}
            className={cn(
              'flex items-center gap-2 rounded-full border px-4 py-2 text-[15px] transition-colors',
              ativa ? 'border-brand bg-subtle font-medium' : 'border-edge bg-surface hover:bg-subtle',
            )}
          >
            {/* A cor vem do cadastro do serviço, como na legenda. */}
            <span className="h-3 w-3 rounded" style={{ backgroundColor: m.cor }} aria-hidden />
            {m.nome}
            {ativa && <Check size={14} aria-hidden />}
          </button>
        )
      })}
    </div>
  )
}
