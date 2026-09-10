import type { Papel } from '@/types/auth'

/**
 * Quem enxerga cada área do sistema.
 *
 * Isto controla apenas o que aparece na tela. A autorização de verdade é do
 * backend, que recusa com 403 mesmo se alguém digitar a URL direto — esconder
 * item de menu não é controle de acesso.
 */
export const ACESSO_POR_ROTA: Record<string, readonly Papel[]> = {
  '/dashboard': ['admin', 'recepcao'],
  // O instrutor entra direto na agenda: é a única tela dele, somente leitura.
  '/agenda': ['admin', 'recepcao', 'instrutor'],
  '/pacientes': ['admin', 'recepcao'],
  // Reposições é operação de balcão: recepção e proprietária.
  '/reposicoes': ['admin', 'recepcao'],
  '/atividades': ['admin', 'recepcao'],
  // Controle financeiro é da proprietária e da recepção, que registra os
  // pagamentos. O instrutor não vê valores.
  '/financeiro': ['admin', 'recepcao'],
}

export function podeAcessar(papel: Papel, rota: string): boolean {
  return ACESSO_POR_ROTA[rota]?.includes(papel) ?? false
}

/** Para onde mandar cada perfil ao entrar. */
export function rotaInicial(papel: Papel): string {
  return papel === 'instrutor' ? '/agenda' : '/dashboard'
}
