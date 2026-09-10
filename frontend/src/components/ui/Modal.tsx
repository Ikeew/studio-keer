import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'

type Props = {
  aberto: boolean
  titulo: string
  onFechar: () => void
  children: ReactNode
}

export function Modal({ aberto, titulo, onFechar, children }: Props) {
  // Esc fecha. Sem isso, quem usa teclado fica preso no modal.
  useEffect(() => {
    if (!aberto) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onFechar()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [aberto, onFechar])

  if (!aberto) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onClick={onFechar}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-card bg-surface shadow-card"
        // O clique dentro do conteúdo não pode fechar o modal.
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-edge px-6 py-5">
          <h2 className="font-heading text-xl font-semibold">{titulo}</h2>
          <button
            type="button"
            onClick={onFechar}
            aria-label="Fechar"
            className="rounded p-1 text-muted transition-colors hover:bg-subtle hover:text-ink"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}
