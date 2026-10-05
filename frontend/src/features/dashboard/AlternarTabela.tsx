type Props = {
  emTabela: boolean
  onAlternar: () => void
}

/** "Ver tabela" / "Ver gráfico": o mesmo dado em forma legível por leitor de tela. */
export function AlternarTabela({ emTabela, onAlternar }: Props) {
  return (
    <button
      type="button"
      onClick={onAlternar}
      className="rounded text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {emTabela ? 'Ver gráfico' : 'Ver tabela'}
    </button>
  )
}
