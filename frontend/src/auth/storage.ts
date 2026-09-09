const CHAVE = 'studio-keer.token'

/**
 * O token fica em localStorage.
 *
 * A alternativa mais segura seria cookie httpOnly, imune a XSS. Ficou de
 * fora nesta entrega porque exigiria CSRF token e domínio compartilhado
 * entre Vercel e Render, e o sistema é interno, sem cadastro público —
 * a superfície de XSS é pequena. Registrado como limitação conhecida em
 * docs/decisoes-tecnicas.md.
 */
export const tokenStorage = {
  ler(): string | null {
    try {
      return localStorage.getItem(CHAVE)
    } catch {
      return null // modo privado, ou storage bloqueado
    }
  },
  gravar(token: string): void {
    try {
      localStorage.setItem(CHAVE, token)
    } catch {
      // sem persistência: a sessão dura só enquanto a aba estiver aberta
    }
  },
  limpar(): void {
    try {
      localStorage.removeItem(CHAVE)
    } catch {
      // nada a fazer
    }
  },
}
