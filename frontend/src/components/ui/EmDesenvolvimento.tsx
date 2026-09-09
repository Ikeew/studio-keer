type Props = {
  fase: string
  descricao: string
}

/** Placeholder de tela ainda não implementada, com a fase que a entrega. */
export function EmDesenvolvimento({ fase, descricao }: Props) {
  return (
    <section className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
      <p className="text-[15px] text-muted">{descricao}</p>
      <p className="mt-3 text-sm text-brand">Entrega prevista: {fase}</p>
    </section>
  )
}
