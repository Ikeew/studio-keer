type Props = {
  tipo?: 'erro' | 'info'
  children: React.ReactNode
}

export function Aviso({ tipo = 'erro', children }: Props) {
  return (
    <p
      role={tipo === 'erro' ? 'alert' : undefined}
      className={
        tipo === 'erro'
          ? 'rounded-card bg-badge-alerta px-4 py-3 text-sm text-ink'
          : 'rounded-card bg-subtle px-4 py-3 text-sm text-muted'
      }
    >
      {children}
    </p>
  )
}
