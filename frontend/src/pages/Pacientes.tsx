import { Plus, Search } from 'lucide-react'
import { useEffect, useState } from 'react'

import { usePacientes } from '@/api/pacientes'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { PacienteCard } from '@/features/pacientes/PacienteCard'
import { PacienteForm } from '@/features/pacientes/PacienteForm'
import { PainelDeMatriculas } from '@/features/matriculas/PainelDeMatriculas'
import type { Paciente } from '@/types/paciente'

const POR_PAGINA = 12

export function Pacientes() {
  const [busca, setBusca] = useState('')
  const [buscaAplicada, setBuscaAplicada] = useState('')
  const [pagina, setPagina] = useState(1)
  const [emEdicao, setEmEdicao] = useState<Paciente | null>(null)
  const [vendoMatriculas, setVendoMatriculas] = useState<Paciente | null>(null)
  const [criando, setCriando] = useState(false)

  // Debounce: sem isso, cada tecla dispara uma requisição.
  useEffect(() => {
    const t = setTimeout(() => {
      setBuscaAplicada(busca)
      setPagina(1)
    }, 300)
    return () => clearTimeout(t)
  }, [busca])

  const { data, isPending, isError } = usePacientes({
    busca: buscaAplicada,
    pagina,
    tamanho: POR_PAGINA,
  })

  const totalPaginas = data ? Math.max(1, Math.ceil(data.total / POR_PAGINA)) : 1

  return (
    <>
      <PageHeader
        title="Pacientes"
        subtitle="Gerencie o cadastro de pacientes"
        action={
          <Button onClick={() => setCriando(true)}>
            <Plus size={20} /> Novo Paciente
          </Button>
        }
      />

      <div className="relative mb-6">
        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar paciente por nome ou telefone…"
          aria-label="Buscar paciente"
          className="w-full rounded-card border border-edge bg-surface py-4 pl-12 pr-4 text-[15px] outline-none focus:border-brand"
        />
      </div>

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar os pacientes.
        </p>
      )}

      {isPending && <p className="text-muted">Carregando…</p>}

      {data && data.itens.length === 0 && (
        <div className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
          <p className="text-muted">
            {buscaAplicada
              ? `Nenhum paciente encontrado para "${buscaAplicada}".`
              : 'Nenhum paciente cadastrado ainda.'}
          </p>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
            {data.itens.map((p) => (
              <PacienteCard
                key={p.id}
                paciente={p}
                onEditar={setEmEdicao}
                onVerMatriculas={setVendoMatriculas}
              />
            ))}
          </div>

          <div className="mt-8 flex items-center justify-between text-[15px]">
            <span className="text-muted">
              {data.total} paciente{data.total === 1 ? '' : 's'}
            </span>
            {totalPaginas > 1 && (
              <div className="flex items-center gap-3">
                <Button
                  variante="secundario"
                  disabled={pagina <= 1}
                  onClick={() => setPagina((p) => p - 1)}
                >
                  Anterior
                </Button>
                <span className="text-muted">
                  {pagina} de {totalPaginas}
                </span>
                <Button
                  variante="secundario"
                  disabled={pagina >= totalPaginas}
                  onClick={() => setPagina((p) => p + 1)}
                >
                  Próxima
                </Button>
              </div>
            )}
          </div>
        </>
      )}

      <Modal aberto={criando} titulo="Novo Paciente" onFechar={() => setCriando(false)}>
        <PacienteForm onPronto={() => setCriando(false)} />
      </Modal>

      <Modal
        aberto={vendoMatriculas !== null}
        titulo={vendoMatriculas ? `Matrículas de ${vendoMatriculas.nome_completo}` : ''}
        onFechar={() => setVendoMatriculas(null)}
      >
        {vendoMatriculas && <PainelDeMatriculas paciente={vendoMatriculas} />}
      </Modal>

      <Modal
        aberto={emEdicao !== null}
        titulo="Editar Paciente"
        onFechar={() => setEmEdicao(null)}
      >
        {emEdicao && (
          <PacienteForm paciente={emEdicao} onPronto={() => setEmEdicao(null)} />
        )}
      </Modal>
    </>
  )
}
