import { AlertTriangle, PackagePlus, Plus, ShoppingBag } from 'lucide-react'
import { useState } from 'react'

import { usePacientes } from '@/api/pacientes'
import {
  useCriarProduto,
  useEntradaDeEstoque,
  useProdutos,
  useVenderProduto,
} from '@/api/produtos'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import { Modal } from '@/components/ui/Modal'
import { cn } from '@/lib/cn'
import { paraCentavos, reais } from '@/lib/formato'
import { FORMAS_PAGAMENTO, FORMA_LABEL, type FormaPagamento } from '@/types/financeiro'
import type { Produto } from '@/types/produto'

function erroDe(e: unknown, padrao: string): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof d === 'string' ? d : padrao
}

/**
 * Estoque de meia e camiseta, no Financeiro.
 *
 * "Bem simples", a pedido da equipe: quanto tem de cada tamanho, vender (dá
 * baixa e lança a cobrança já paga), repor, e um aviso quando está acabando.
 */
export function Estoque({ ehAdmin }: { ehAdmin: boolean }) {
  const { data: produtos } = useProdutos()
  const [vendendo, setVendendo] = useState<Produto | null>(null)
  const [repondo, setRepondo] = useState<Produto | null>(null)
  const [criando, setCriando] = useState(false)

  if (!produtos) return null
  if (produtos.length === 0 && !ehAdmin) return null

  const acabando = produtos.filter((p) => p.acabando).length

  return (
    <section aria-labelledby="titulo-estoque" className="mb-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 id="titulo-estoque" className="font-heading text-lg font-semibold">
          Produtos
          {acabando > 0 && (
            <span className="ml-3 rounded-full bg-badge-alerta px-3 py-1 text-sm font-normal">
              {acabando} acabando
            </span>
          )}
        </h2>
        {ehAdmin && (
          <Button variante="secundario" className="px-4 py-2 text-sm" onClick={() => setCriando(true)}>
            <Plus size={16} /> Novo produto
          </Button>
        )}
      </div>

      {produtos.length === 0 ? (
        <p className="rounded-card border border-dashed border-edge bg-surface p-6 text-center text-muted">
          Nenhum produto cadastrado. Cadastre um por tamanho (ex.: Camiseta P, Camiseta M).
        </p>
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {produtos.map((p) => (
            <li
              key={p.id}
              className={cn(
                'flex flex-col rounded-card border bg-surface p-4 shadow-card',
                p.acabando ? 'border-danger/40' : 'border-edge',
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">
                    {p.nome} <span className="text-muted">· {p.tamanho}</span>
                  </p>
                  <p className="text-sm text-muted">{reais(p.preco_centavos)}</p>
                </div>
                {p.acabando && (
                  <span
                    className="flex items-center gap-1 rounded-full bg-badge-alerta px-2 py-0.5 text-sm"
                    title={`Mínimo: ${p.estoque_minimo}`}
                  >
                    <AlertTriangle size={14} aria-hidden />
                    {p.estoque === 0 ? 'Esgotado' : 'Acabando'}
                  </span>
                )}
              </div>
              <p className="mt-3 font-heading text-3xl font-semibold tabular-nums">
                {p.estoque}
                <span className="ml-1 text-sm font-normal text-muted">em estoque</span>
              </p>
              <div className="mt-4 flex gap-2">
                <Button
                  variante="acento"
                  className="flex-1 px-3 py-2 text-sm"
                  disabled={p.estoque === 0}
                  onClick={() => setVendendo(p)}
                >
                  <ShoppingBag size={16} /> Vender
                </Button>
                <Button
                  variante="secundario"
                  className="flex-1 px-3 py-2 text-sm"
                  onClick={() => setRepondo(p)}
                >
                  <PackagePlus size={16} /> Entrada
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal
        aberto={vendendo !== null}
        titulo={vendendo ? `Vender ${vendendo.nome} ${vendendo.tamanho}` : ''}
        onFechar={() => setVendendo(null)}
      >
        {vendendo && <FormularioDeVenda produto={vendendo} onPronto={() => setVendendo(null)} />}
      </Modal>
      <Modal
        aberto={repondo !== null}
        titulo={repondo ? `Entrada de ${repondo.nome} ${repondo.tamanho}` : ''}
        onFechar={() => setRepondo(null)}
      >
        {repondo && <FormularioDeEntrada produto={repondo} onPronto={() => setRepondo(null)} />}
      </Modal>
      <Modal aberto={criando} titulo="Novo produto" onFechar={() => setCriando(false)}>
        {criando && <FormularioDeProduto onPronto={() => setCriando(false)} />}
      </Modal>
    </section>
  )
}

function FormularioDeVenda({ produto, onPronto }: { produto: Produto; onPronto: () => void }) {
  const [quantidade, setQuantidade] = useState('1')
  const [pacienteId, setPacienteId] = useState('')
  const [comprador, setComprador] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const { data: pagina } = usePacientes({ tamanho: 100 })
  const vender = useVenderProduto()

  const qtd = Number(quantidade)
  const valida = Number.isInteger(qtd) && qtd >= 1 && qtd <= produto.estoque

  async function vendaCom(forma: FormaPagamento) {
    setErro(null)
    try {
      await vender.mutateAsync({
        id: produto.id,
        quantidade: qtd,
        forma_pagamento: forma,
        patient_id: pacienteId ? Number(pacienteId) : null,
        comprador_nome: pacienteId ? null : comprador.trim() || null,
      })
      onPronto()
    } catch (e) {
      setErro(erroDe(e, 'Não foi possível registrar a venda.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Campo id="venda-qtd" label={`Quantidade (há ${produto.estoque})`} obrigatorio>
        <Input
          id="venda-qtd"
          type="number"
          min={1}
          max={produto.estoque}
          value={quantidade}
          onChange={(e) => setQuantidade(e.target.value)}
        />
      </Campo>

      <Campo id="venda-paciente" label="Paciente">
        <Select id="venda-paciente" value={pacienteId} onChange={(e) => setPacienteId(e.target.value)}>
          <option value="">Não é paciente</option>
          {(pagina?.itens ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.nome_completo}
            </option>
          ))}
        </Select>
      </Campo>
      {!pacienteId && (
        <Campo id="venda-comprador" label="Nome de quem comprou">
          <Input
            id="venda-comprador"
            placeholder="Em branco: Studio Keer"
            value={comprador}
            onChange={(e) => setComprador(e.target.value)}
          />
        </Campo>
      )}

      <p className="font-heading text-2xl font-semibold">
        {reais(produto.preco_centavos * (valida ? qtd : 0))}
      </p>

      {/* A venda é de balcão: já sai paga. Escolher a forma é concluir. */}
      <div role="group" aria-label="Como pagou?" className="flex flex-col gap-2">
        <p className="text-[15px] font-medium">Como pagou?</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {FORMAS_PAGAMENTO.map((forma) => (
            <button
              key={forma}
              type="button"
              disabled={!valida || vender.isPending}
              onClick={() => vendaCom(forma)}
              className="rounded-card border border-edge px-4 py-3 text-[15px] font-medium transition-colors hover:border-brand hover:bg-subtle disabled:opacity-50"
            >
              {FORMA_LABEL[forma]}
            </button>
          ))}
        </div>
      </div>

      {erro && <Aviso>{erro}</Aviso>}
    </div>
  )
}

function FormularioDeEntrada({ produto, onPronto }: { produto: Produto; onPronto: () => void }) {
  const [quantidade, setQuantidade] = useState('')
  const [observacao, setObservacao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const entrada = useEntradaDeEstoque()
  const qtd = Number(quantidade)

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[15px] text-muted">Hoje há {produto.estoque} em estoque.</p>
      <Campo id="entrada-qtd" label="Quantas chegaram" obrigatorio>
        <Input
          id="entrada-qtd"
          type="number"
          min={1}
          autoFocus
          value={quantidade}
          onChange={(e) => setQuantidade(e.target.value)}
        />
      </Campo>
      <Campo id="entrada-obs" label="Observação">
        <Input id="entrada-obs" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
      </Campo>
      {erro && <Aviso>{erro}</Aviso>}
      <Button
        disabled={!Number.isInteger(qtd) || qtd < 1 || entrada.isPending}
        onClick={async () => {
          setErro(null)
          try {
            await entrada.mutateAsync({ id: produto.id, quantidade: qtd, observacao })
            onPronto()
          } catch (e) {
            setErro(erroDe(e, 'Não foi possível registrar a entrada.'))
          }
        }}
      >
        Registrar entrada
      </Button>
    </div>
  )
}

function FormularioDeProduto({ onPronto }: { onPronto: () => void }) {
  const [nome, setNome] = useState('')
  const [tamanho, setTamanho] = useState('')
  const [preco, setPreco] = useState('')
  const [minimo, setMinimo] = useState('3')
  const [erro, setErro] = useState<string | null>(null)
  const criar = useCriarProduto()
  const centavos = paraCentavos(preco)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4">
        <Campo id="prod-nome" label="Produto" obrigatorio>
          <Input id="prod-nome" placeholder="Camiseta" value={nome} onChange={(e) => setNome(e.target.value)} />
        </Campo>
        <Campo id="prod-tamanho" label="Tamanho" obrigatorio>
          <Input
            id="prod-tamanho"
            placeholder="P, M, G ou Único"
            value={tamanho}
            onChange={(e) => setTamanho(e.target.value)}
          />
        </Campo>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <Campo id="prod-preco" label="Preço (R$)" obrigatorio>
          <Input id="prod-preco" inputMode="decimal" placeholder="45,00" value={preco} onChange={(e) => setPreco(e.target.value)} />
        </Campo>
        <Campo id="prod-minimo" label="Avisar quando chegar a">
          <Input
            id="prod-minimo"
            type="number"
            min={0}
            value={minimo}
            onChange={(e) => setMinimo(e.target.value)}
          />
        </Campo>
      </div>
      <p className="-mt-2 text-sm text-muted">
        Cada tamanho é um produto: o estoque acaba por tamanho.
      </p>
      {erro && <Aviso>{erro}</Aviso>}
      <Button
        disabled={nome.trim().length < 2 || !tamanho.trim() || centavos === null || criar.isPending}
        onClick={async () => {
          if (centavos === null) return
          setErro(null)
          try {
            await criar.mutateAsync({
              nome: nome.trim(),
              tamanho: tamanho.trim(),
              preco_centavos: centavos,
              estoque_minimo: Math.max(0, Math.floor(Number(minimo) || 0)),
            })
            onPronto()
          } catch (e) {
            setErro(erroDe(e, 'Não foi possível cadastrar o produto.'))
          }
        }}
      >
        Cadastrar
      </Button>
    </div>
  )
}
