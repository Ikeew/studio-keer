import { useEffect } from 'react'

/**
 * Atualiza document.title para cada rota, permitindo que leitores de tela
 * anunciem a mudança de contexto ao navegar em SPA.
 *
 * Formato: "<Página> · Studio Keer"
 */
export function usePageTitle(pagina: string) {
  useEffect(() => {
    document.title = `${pagina} · Studio Keer`
    return () => {
      document.title = 'Studio Keer'
    }
  }, [pagina])
}
