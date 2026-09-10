import type { SessaoNaGrade } from '@/types/agenda'

type Props = { sessoes: SessaoNaGrade[] }

/**
 * Legenda de cores, como no print.
 *
 * Derivada das sessões que estão na tela, e não de uma consulta a
 * `/services`: o instrutor não tem acesso ao catálogo de serviços (é somente
 * leitura da agenda), e pedir a rota só para montar a legenda gerava 403 no
 * console dele. De quebra, a legenda passa a listar só o que aparece na
 * semana, em vez de serviços que não têm turma nenhuma.
 */
export function Legenda({ sessoes }: Props) {
  const servicos = new Map<string, string>()
  sessoes.forEach((s) => servicos.set(s.servico_nome, s.servico_cor))

  if (servicos.size === 0) return null

  return (
    <div className="mb-6 flex flex-wrap items-center gap-5 text-[15px]">
      {[...servicos].map(([nome, cor]) => (
        <span key={nome} className="flex items-center gap-2">
          <span className="h-4 w-4 rounded" style={{ backgroundColor: cor }} aria-hidden />
          {nome}
        </span>
      ))}
      <span className="flex items-center gap-2">
        <span className="h-4 w-4 rounded bg-falta" aria-hidden />
        Faltou
      </span>
    </div>
  )
}
