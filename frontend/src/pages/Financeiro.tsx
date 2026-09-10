import { AlertCircle, DollarSign, Pencil, Plus, RefreshCw, Search } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  useCancelarCobranca,
  useCobrancas,
  useDesfazerPagamento,
  useGerarMensalidades,
  useMarcarPago,
  useTotais,
} from '@/api/financeiro'
import { useAuth } from '@/auth/useAuth'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { VendaDePacote } from '@/features/financeiro/VendaDePacote'
import { cn } from '@/lib/cn'
import { data as formatarData, reais } from '@/lib/formato'
import { FILTROS, type Cobranca } from '@/types/financeiro'

function CardDeTotal({
  rotulo,
  valor,
  cor,
  alerta,
}: {
  rotulo: string
  valor: number
  cor: string
  alerta?: boolean
}) {
  return (
    <div className="rounded-card border border-edge bg-surface p-6 shadow-card">
      <div className="flex items-start justify-between">
        <span className="text-[15px] text-muted">{rotulo}</span>
        <span
          className={cn(
            'flex h-9 w-9 items-center justify-center rounded-card',
            alerta ? 'bg-badge-alerta' : 'bg-subtle',
          )}
        >
          {alerta ? (
            <AlertCircle size={18} className="text-danger" />
          ) : (
            <DollarSign size={18} className="text-muted" />
          )}
        </span>
      </div>
      <p className={cn('mt-3 font-heading text-3xl font-semibold', cor)}>
        {reais(valor)}
      </p>
    </div>
  )
}

export function Financeiro() {
  const { usuario } = useAuth()
  const ehAdmin = usuario?.papel === 'admin'

  const [filtro, setFiltro] = useState<string | null>(null)
  const [busca, setBusca] = useState('')
  const [buscaAplicada, setBuscaAplicada] = useState('')
  const [vendendo, setVendendo] = useState(false)
  const [cancelando, setCancelando] = useState<Cobranca | null>(null)
  const [motivo, setMotivo] = useState('')
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca), 300)
    return () => clearTimeout(t)
  }, [busca])

  const { data: totais } = useTotais()
  const { data: pagina, isPending } = useCobrancas({ filtro, busca: buscaAplicada })
  const pagar = useMarcarPago()
  const desfazer = useDesfazerPagamento()
  const cancelar = useCancelarCobranca()
  const gerar = useGerarMensalidades()

  return (
    <>
      <PageHeader
        title="Financeiro"
        subtitle="Controle de pagamentos"
        action={
          <div className="flex gap-3">
            <Button variante="secundario" onClick={() => setVendendo(true)}>
              <Plus size={18} /> Vender pacote
            </Button>
            <Button
              disabled={gerar.isPending}
              onClick={async () => {
                const r = await gerar.mutateAsync(undefined)
                setAviso(
                  `${r.criadas} mensalidade${r.criadas === 1 ? '' : 's'} emitida${
                    r.criadas === 1 ? '' : 's'
                  } · ${r.ja_existentes} já existia${r.ja_existentes === 1 ? '' : 'm'}`,
                )
              }}
            >
              <RefreshCw size={18} />
              {gerar.isPending ? 'Emitindo…' : 'Emitir mensalidades'}
            </Button>
          </div>
        }
      />

      {aviso && <Aviso tipo="info">{aviso}</Aviso>}

      <div className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-3">
        <CardDeTotal
          rotulo="Total Recebido"
          valor={totais?.recebido_centavos ?? 0}
          cor="text-accent"
        />
        <CardDeTotal
          rotulo="Total Pendente"
          valor={totais?.pendente_centavos ?? 0}
          cor="text-brand"
        />
        <CardDeTotal
          rotulo="Total Vencido"
          valor={totais?.vencido_centavos ?? 0}
          cor="text-danger"
          alerta
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        {FILTROS.map((f) => (
          <button
            key={f.rotulo}
            type="button"
            onClick={() => setFiltro(f.valor)}
            className={cn(
              'rounded-card px-5 py-3 text-[15px] font-medium transition-colors',
              filtro === f.valor ? 'bg-brand text-white' : 'bg-edge text-ink hover:bg-edge/70',
            )}
          >
            {f.rotulo}
          </button>
        ))}
        <div className="relative ml-auto min-w-[280px] flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por paciente ou descrição…"
            aria-label="Buscar cobrança"
            className="w-full rounded-card border border-edge bg-surface py-3 pl-10 pr-4 text-[15px] outline-none focus:border-brand"
          />
        </div>
      </div>

      {isPending && <p className="text-muted">Carregando…</p>}

      {pagina && pagina.itens.length === 0 && (
        <div className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
          <p className="text-muted">Nenhuma cobrança nesta visão.</p>
        </div>
      )}

      {pagina && pagina.itens.length > 0 && (
        <div className="overflow-x-auto rounded-card border border-edge bg-surface shadow-card">
          <table className="w-full">
            <thead className="bg-subtle text-left">
              <tr>
                <th className="p-4 font-medium">Paciente</th>
                <th className="p-4 font-medium">Descrição</th>
                <th className="p-4 font-medium">Valor</th>
                <th className="p-4 font-medium">Vencimento</th>
                <th className="p-4 font-medium">Status</th>
                <th className="p-4 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {pagina.itens.map((c) => (
                <tr key={c.id} className="border-t border-edge">
                  <td className="p-4">{c.paciente_nome}</td>
                  <td className="p-4 text-muted">{c.descricao}</td>
                  <td className="p-4 font-medium">{reais(c.valor_centavos)}</td>
                  <td className="p-4">
                    {formatarData(c.vencimento)}
                    {c.vencida && (
                      <span className="ml-2 text-sm text-danger">
                        {c.dias_de_atraso}d em atraso
                      </span>
                    )}
                  </td>
                  <td className="p-4">
                    <span
                      className={cn(
                        'rounded-full px-3 py-1 text-sm',
                        c.status === 'pago' && 'bg-badge-pago',
                        c.status === 'pendente' && !c.vencida && 'bg-badge-aguardando',
                        c.status === 'pendente' && c.vencida && 'bg-badge-alerta',
                        c.status === 'cancelado' && 'bg-edge text-muted',
                      )}
                    >
                      {/* "Vencido" é derivado, não um status gravado. */}
                      {c.status === 'pendente' && c.vencida
                        ? 'Vencido'
                        : c.status === 'pago'
                          ? 'Pago'
                          : c.status === 'cancelado'
                            ? 'Cancelado'
                            : 'Pendente'}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      {c.status === 'pendente' && (
                        <Button
                          variante="acento"
                          className="px-4 py-2 text-sm"
                          onClick={() => pagar.mutate({ id: c.id, forma: 'pix' })}
                        >
                          Marcar Pago
                        </Button>
                      )}
                      {c.status === 'pago' && (
                        <Button
                          variante="secundario"
                          className="px-4 py-2 text-sm"
                          onClick={() => desfazer.mutate(c.id)}
                        >
                          Desfazer
                        </Button>
                      )}
                      {ehAdmin && c.status !== 'cancelado' && (
                        <button
                          type="button"
                          aria-label="Cancelar cobrança"
                          title="Cancelar cobrança (só a proprietária)"
                          onClick={() => {
                            setCancelando(c)
                            setMotivo('')
                          }}
                          className="rounded p-2 text-muted transition-colors hover:bg-subtle hover:text-danger"
                        >
                          <Pencil size={16} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pagina && (
        <p className="mt-4 text-[15px] text-muted">
          {pagina.total} cobrança{pagina.total === 1 ? '' : 's'}
        </p>
      )}

      <Modal aberto={vendendo} titulo="Vender Pacote" onFechar={() => setVendendo(false)}>
        <VendaDePacote onPronto={() => setVendendo(false)} />
      </Modal>

      <Modal
        aberto={cancelando !== null}
        titulo="Cancelar cobrança"
        onFechar={() => setCancelando(null)}
      >
        {cancelando && (
          <div className="flex flex-col gap-4">
            <p className="text-[15px]">
              Cancelar <strong>{cancelando.descricao}</strong> de{' '}
              <strong>{cancelando.paciente_nome}</strong>? A cobrança deixa de ser
              devida.
            </p>
            <input
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Motivo do cancelamento"
              aria-label="Motivo do cancelamento"
              className="w-full rounded-card border border-edge px-4 py-3 outline-none focus:border-brand"
            />
            <div className="flex gap-3">
              <Button
                className="flex-1"
                disabled={!motivo.trim()}
                onClick={async () => {
                  await cancelar.mutateAsync({ id: cancelando.id, motivo })
                  setCancelando(null)
                }}
              >
                Cancelar cobrança
              </Button>
              <Button
                variante="secundario"
                className="flex-1"
                onClick={() => setCancelando(null)}
              >
                Voltar
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  )
}
