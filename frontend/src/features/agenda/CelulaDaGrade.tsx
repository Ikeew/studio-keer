import { cn } from '@/lib/cn'
import type { SessaoNaGrade } from '@/types/agenda'

type Props = {
  sessoes: SessaoNaGrade[]
  aberto: boolean
  onAbrirSessao: (s: SessaoNaGrade) => void
}

/**
 * Uma célula da grade: hora × dia.
 *
 * Célula sem turma diz "Sem turma", e NÃO "Disponível". A diferença importa:
 * horário sem sessão materializada não é vaga que se possa oferecer — ver a
 * armadilha da materialização em `schedule_service.sessoes_com_vaga`.
 */
export function CelulaDaGrade({ sessoes, aberto, onAbrirSessao }: Props) {
  if (!aberto) {
    return <td className="border border-edge bg-subtle" aria-label="Fechado" />
  }

  if (sessoes.length === 0) {
    return (
      <td className="border border-edge p-2 align-top">
        <span className="text-sm italic text-muted">Sem turma</span>
      </td>
    )
  }

  return (
    <td className="border border-edge p-2 align-top">
      <div className="flex flex-col gap-2">
        {sessoes.map((sessao) => {
          const vagasTexto = sessao.lotada
            ? 'Turma cheia'
            : `${sessao.vagas} vaga${sessao.vagas === 1 ? '' : 's'}`

          // Rótulo descritivo para leitores de tela: contexto completo da célula.
          const label = `${sessao.servico_nome}, ${sessao.instrutor_nome}, ${vagasTexto}`

          return (
            <button
              key={sessao.id}
              type="button"
              onClick={() => onAbrirSessao(sessao)}
              onKeyDown={(e) => {
                // Enter e Espaço já disparam onClick em buttons nativos,
                // mas garantimos explicitamente para leitores de tela.
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onAbrirSessao(sessao)
                }
              }}
              aria-label={label}
              className="w-full rounded-card border-l-4 bg-subtle p-2 text-left transition-colors hover:bg-edge focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1"
              style={{ borderLeftColor: sessao.servico_cor }}
            >
              {/* Conteúdo visual — o aria-label no button já descreve tudo. */}
              <span className="block text-sm font-medium" aria-hidden="true">
                {sessao.servico_nome}
              </span>
              {/* Os prints omitem o instrutor. A interface DEVE mostrá-lo —
                  sem isso o perfil de instrutor não tem o que ler. */}
              <span className="block text-sm text-muted" aria-hidden="true">
                {sessao.instrutor_nome}
              </span>

              <ul className="mt-1 flex flex-col gap-0.5" aria-label="Alunos">
                {sessao.reservas.map((r) => (
                  <li
                    key={r.id}
                    className={cn(
                      'truncate text-sm',
                      r.status === 'falta' && 'text-falta line-through',
                      r.status === 'presente' && 'text-ink',
                    )}
                  >
                    {r.paciente_nome}
                    {r.origem === 'reposicao' && (
                      <span className="ml-1 text-xs text-muted">(rep.)</span>
                    )}
                  </li>
                ))}
              </ul>

              <span
                className={cn(
                  'mt-1 block text-sm font-medium',
                  sessao.lotada ? 'text-falta' : 'text-muted',
                )}
                aria-hidden="true"
              >
                {vagasTexto}
              </span>
            </button>
          )
        })}
      </div>
    </td>
  )
}
