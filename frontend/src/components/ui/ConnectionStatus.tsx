import { useHealth } from '@/api/health'

/**
 * Andaime da Fase 0: mostra se o frontend alcança a API e se a API alcança o
 * Postgres. Sai do projeto quando o Dashboard real entrar (Fase 6).
 */
export function ConnectionStatus() {
  const { data, isPending, isError } = useHealth()

  const linha = isPending
    ? 'Verificando conexão com a API…'
    : isError
      ? 'API inacessível — o backend está no ar?'
      : `API respondendo · banco de dados: ${data.database}`

  const ok = !isPending && !isError && data.database === 'ok'

  return (
    <section className="rounded-card border border-edge bg-surface p-6 shadow-card">
      <h2 className="font-heading text-lg font-semibold">Status da instalação</h2>
      <p className="mt-2 text-[15px] text-muted">{linha}</p>
      <span
        className={
          ok
            ? 'mt-4 inline-block rounded-full bg-badge-confirmado px-3 py-1 text-sm text-ink'
            : 'mt-4 inline-block rounded-full bg-badge-alerta px-3 py-1 text-sm text-ink'
        }
      >
        {ok ? 'Tudo conectado' : 'Verificar ambiente'}
      </span>
    </section>
  )
}
