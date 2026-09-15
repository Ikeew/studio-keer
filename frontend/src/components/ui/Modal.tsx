import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'

type Props = {
  aberto: boolean
  titulo: string
  onFechar: () => void
  children: ReactNode
}

/** Seletores de elementos focáveis para o focus trap. */
const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Modal({ aberto, titulo, onFechar, children }: Props) {
  const tituloId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  /** Guarda quem estava focado antes de abrir para devolver ao fechar. */
  const gatilhoRef = useRef<Element | null>(null)

  // Captura o elemento com foco no momento da abertura.
  useEffect(() => {
    if (aberto) {
      gatilhoRef.current = document.activeElement
    }
  }, [aberto])

  // Move o foco para dentro do modal ao abrir; devolve ao fechar.
  useEffect(() => {
    if (!aberto) {
      // Devolve o foco ao elemento que abriu o modal.
      if (gatilhoRef.current instanceof HTMLElement) {
        gatilhoRef.current.focus()
      }
      return
    }

    // Pequeno tick para garantir que o DOM já renderizou o conteúdo.
    const timer = setTimeout(() => {
      const primeiro = dialogRef.current?.querySelectorAll<HTMLElement>(FOCAVEIS)[0]
      primeiro?.focus()
    }, 0)

    return () => clearTimeout(timer)
  }, [aberto])

  // Esc fecha; Tab fica preso dentro do modal (focus trap).
  useEffect(() => {
    if (!aberto) return

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onFechar()
        return
      }

      if (e.key !== 'Tab') return

      const dialog = dialogRef.current
      if (!dialog) return

      const focaveis = Array.from(dialog.querySelectorAll<HTMLElement>(FOCAVEIS)).filter(
        (el) => !el.closest('[aria-hidden="true"]'),
      )
      if (focaveis.length === 0) return

      const primeiro = focaveis[0]
      const ultimo = focaveis[focaveis.length - 1]

      if (e.shiftKey) {
        // Shift+Tab no primeiro elemento → vai para o último.
        if (document.activeElement === primeiro) {
          e.preventDefault()
          ultimo.focus()
        }
      } else {
        // Tab no último elemento → volta para o primeiro.
        if (document.activeElement === ultimo) {
          e.preventDefault()
          primeiro.focus()
        }
      }
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
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-card bg-surface shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-edge px-6 py-5">
          <h2 id={tituloId} className="font-heading text-xl font-semibold">
            {titulo}
          </h2>
          <button
            type="button"
            onClick={onFechar}
            aria-label="Fechar"
            className="rounded p-1 text-muted transition-colors hover:bg-subtle hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}
