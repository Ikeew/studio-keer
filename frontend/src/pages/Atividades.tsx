import { Activity, Plus, Users } from 'lucide-react'
import { useState } from 'react'

import { useEstatisticasDeServicos } from '@/api/dashboard'
import { useServicos } from '@/api/servicos'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { PageHeader } from '@/components/ui/PageHeader'
import { usePageTitle } from '@/hooks/usePageTitle'
import { ServicoForm } from '@/features/atividades/ServicoForm'
import { reais } from '@/lib/formato'
import { MODELO_COBRANCA_LABEL, type Servico } from '@/types/servico'

function ServicoCard({
  servico,
  onEditar,
}: {
  servico: Servico
  onEditar: (s: Servico) => void
}) {
  return (
    <article className="flex flex-col rounded-card border border-edge bg-surface p-6 shadow-card">
      <div
        className="flex h-12 w-12 items-center justify-center rounded-card text-white"
        style={{ backgroundColor: servico.cor }}
      >
        <Activity size={24} />
      </div>

      <h3 className="mt-4 font-heading text-xl font-semibold">{servico.nome}</h3>

      <div className="mt-4 flex items-baseline justify-between">
        <span className="text-[15px] text-muted">{servico.duracao_min} min</span>
        <span className="text-xl font-semibold text-brand">
          {reais(servico.preco_centavos)}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="flex items-center gap-1 rounded-full bg-subtle px-3 py-1 text-muted">
          <Users size={14} />
          {servico.capacidade_padrao === 1
            ? 'Individual'
            : `Até ${servico.capacidade_padrao} por turma`}
        </span>
        <span className="rounded-full bg-subtle px-3 py-1 text-muted">
          {MODELO_COBRANCA_LABEL[servico.modelo_cobranca]}
        </span>
      </div>

      {servico.modelo_cobranca === 'pacote' && servico.sugestao_pacote_sessoes && (
        <p className="mt-3 text-sm text-muted">
          Sugestão: {servico.sugestao_pacote_sessoes} sessões
          {servico.sugestao_pacote_valor_centavos
            ? ` · ${reais(servico.sugestao_pacote_valor_centavos)}`
            : ''}
          {servico.sugestao_pacote_validade_dias
            ? ` · ${servico.sugestao_pacote_validade_dias} dias`
            : ''}
        </p>
      )}

      {/* mt-auto empurra o bloco para a base do card: sem isso, cards de
          alturas diferentes na mesma linha ficam com os botões desalinhados. */}
      <div className="mt-auto pt-5">
        <button
          type="button"
          onClick={() => onEditar(servico)}
          className="w-full rounded-card bg-edge py-3 text-[15px] font-medium transition-colors hover:bg-edge/70"
        >
          Editar Serviço
        </button>
      </div>
    </article>
  )
}

function EstatisticasDeServicos() {
  const { data: stats } = useEstatisticasDeServicos()
  if (!stats || stats.length === 0) return null

  return (
    <section className="mt-8 rounded-card border border-edge bg-surface p-6 shadow-card">
      <h2 className="font-heading text-xl font-semibold">Estatísticas de Serviços</h2>
      <p className="mt-1 text-sm text-muted">Mês corrente</p>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        {stats.map((s) => (
          <div
            key={s.service_id}
            className="rounded-card p-5 text-center"
            // Mesma cor do serviço na agenda, bem clara: a associação entre
            // legenda e estatística fica imediata.
            style={{ backgroundColor: `${s.cor}1A` }}
          >
            <p className="font-heading text-3xl font-semibold" style={{ color: s.cor }}>
              {s.reservas_no_mes}
            </p>
            <p className="mt-1 text-[15px]">{s.nome}</p>
            <p className="mt-1 text-sm text-muted">
              {s.sessoes_no_mes} turma{s.sessoes_no_mes === 1 ? '' : 's'} ·{' '}
              {s.ocupacao_percentual}% de ocupação
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}

export function Atividades() {
  usePageTitle('Atividades & Serviços')
  const { data: servicos, isPending, isError } = useServicos()
  const [criando, setCriando] = useState(false)
  const [emEdicao, setEmEdicao] = useState<Servico | null>(null)

  return (
    <>
      <PageHeader
        title="Atividades & Serviços"
        subtitle="Gerencie os serviços oferecidos"
        action={
          <Button onClick={() => setCriando(true)}>
            <Plus size={20} /> Nova Atividade
          </Button>
        }
      />

      {isError && (
        <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3">
          Não foi possível carregar os serviços.
        </p>
      )}
      {isPending && <p className="text-muted">Carregando…</p>}

      {servicos && servicos.length === 0 && (
        <div className="rounded-card border border-dashed border-edge bg-surface p-10 text-center">
          <p className="text-muted">Nenhum serviço cadastrado ainda.</p>
        </div>
      )}

      {servicos && servicos.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
          {servicos.map((s) => (
            <ServicoCard key={s.id} servico={s} onEditar={setEmEdicao} />
          ))}
        </div>
      )}

      <EstatisticasDeServicos />

      <Modal
        aberto={criando}
        titulo="Adicionar Nova Atividade"
        onFechar={() => setCriando(false)}
      >
        <ServicoForm onPronto={() => setCriando(false)} />
      </Modal>

      <Modal
        aberto={emEdicao !== null}
        titulo="Editar Serviço"
        onFechar={() => setEmEdicao(null)}
      >
        {emEdicao && <ServicoForm servico={emEdicao} onPronto={() => setEmEdicao(null)} />}
      </Modal>
    </>
  )
}
