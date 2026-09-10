import { useEffect, useState } from 'react'

import { usePacientes } from '@/api/pacientes'
import { useServicos } from '@/api/servicos'
import { useSugestaoDePacote, useVenderPacote } from '@/api/financeiro'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'

/**
 * Venda de pacote.
 *
 * Cada pacote é NEGOCIADO no ato pela doutora. A sugestão do serviço apenas
 * pré-preenche o formulário; todos os campos ficam editáveis, e o que for
 * gravado vira snapshot — depois de vendido, o pacote nunca relê o serviço.
 */
export function VendaDePacote({ onPronto }: { onPronto: () => void }) {
  const [erro, setErro] = useState<string | null>(null)
  const [pacienteId, setPacienteId] = useState('')
  const [servicoId, setServicoId] = useState('')
  const [sessoes, setSessoes] = useState('')
  const [valor, setValor] = useState('')
  const [validade, setValidade] = useState('')

  const { data: pagina } = usePacientes({ tamanho: 100 })
  const { data: servicos } = useServicos()
  const { data: sugestao } = useSugestaoDePacote(servicoId ? Number(servicoId) : null)
  const vender = useVenderPacote()

  const pacotes = servicos?.filter((s) => s.modelo_cobranca === 'pacote') ?? []

  // Pré-preenche ao escolher o serviço. Só sugere: o que a doutora digitar
  // por cima é o que vale.
  useEffect(() => {
    if (!sugestao) return
    if (sugestao.sessoes !== null) setSessoes(String(sugestao.sessoes))
    if (sugestao.valor_centavos !== null) setValor(String(sugestao.valor_centavos / 100))
    if (sugestao.validade_dias !== null) {
      const d = new Date()
      d.setDate(d.getDate() + sugestao.validade_dias)
      setValidade(d.toISOString().slice(0, 10))
    }
  }, [sugestao])

  return (
    <div className="flex flex-col gap-4">
      <Campo id="pkg-paciente" label="Paciente" obrigatorio>
        <Select
          id="pkg-paciente"
          value={pacienteId}
          onChange={(e) => setPacienteId(e.target.value)}
        >
          <option value="">Selecione…</option>
          {(pagina?.itens ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.nome_completo}
            </option>
          ))}
        </Select>
      </Campo>

      <Campo id="pkg-servico" label="Serviço" obrigatorio>
        <Select
          id="pkg-servico"
          value={servicoId}
          onChange={(e) => setServicoId(e.target.value)}
        >
          <option value="">Selecione…</option>
          {pacotes.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome}
            </option>
          ))}
        </Select>
      </Campo>

      {servicoId && (
        <p className="rounded-card bg-subtle px-4 py-3 text-sm text-muted">
          Os campos abaixo vêm pré-preenchidos com a sugestão do serviço. Ajuste
          conforme o combinado com o paciente — o que ficar aqui é o que vale.
        </p>
      )}

      <div className="grid grid-cols-2 gap-4">
        <Campo id="pkg-sessoes" label="Sessões contratadas" obrigatorio>
          <Input
            id="pkg-sessoes"
            type="number"
            min={1}
            value={sessoes}
            onChange={(e) => setSessoes(e.target.value)}
          />
        </Campo>
        <Campo id="pkg-valor" label="Valor total (R$)" obrigatorio>
          <Input
            id="pkg-valor"
            type="number"
            min={0}
            step="0.01"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
        </Campo>
      </div>

      <Campo id="pkg-validade" label="Validade">
        <Input
          id="pkg-validade"
          type="date"
          value={validade}
          onChange={(e) => setValidade(e.target.value)}
        />
      </Campo>
      <p className="-mt-2 text-sm text-muted">
        Em branco significa que vale até acabar o saldo. Como falta não consome
        sessão, a validade é a única coisa que encerra um pacote.
      </p>

      {erro && <Aviso>{erro}</Aviso>}

      <div className="mt-2 flex gap-3">
        <Button
          className="flex-1"
          disabled={!pacienteId || !servicoId || !sessoes || !valor}
          onClick={async () => {
            setErro(null)
            try {
              await vender.mutateAsync({
                patient_id: Number(pacienteId),
                service_id: Number(servicoId),
                sessoes_contratadas: Number(sessoes),
                valor_centavos: Math.round(Number(valor) * 100),
                validade_ate: validade || null,
              })
              onPronto()
            } catch (e) {
              const d = (e as { response?: { data?: { detail?: unknown } } })?.response
                ?.data?.detail
              setErro(typeof d === 'string' ? d : 'Não foi possível registrar a venda.')
            }
          }}
        >
          Vender pacote
        </Button>
        <Button variante="secundario" className="flex-1" onClick={onPronto}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
