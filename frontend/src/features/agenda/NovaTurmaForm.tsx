import { useState } from 'react'

import { useCriarSessao } from '@/api/agenda'
import { useServicos } from '@/api/servicos'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import type { DiaDaGrade } from '@/types/agenda'
import { DIA_LABEL } from '@/types/agenda'

type Props = {
  dias: DiaDaGrade[]
  instrutores: { id: number; nome: string }[]
  onPronto: () => void
}

export function NovaTurmaForm({ dias, instrutores, onPronto }: Props) {
  const abertos = dias.filter((d) => d.aberto)
  const [erro, setErro] = useState<string | null>(null)
  const [dia, setDia] = useState(abertos[0]?.data ?? '')
  const [hora, setHora] = useState('')
  const [servicoId, setServicoId] = useState('')
  const [instrutorId, setInstrutorId] = useState('')
  const [capacidade, setCapacidade] = useState('')

  const { data: servicos } = useServicos()
  const criar = useCriarSessao()

  // As horas vêm da API já SEM a pausa e sem o que está fora da janela: a
  // tela não precisa saber que existe pausa, e não há como escolher 13:00.
  const horasDoDia = abertos.find((d) => d.data === dia)?.horas ?? []

  return (
    <div className="flex flex-col gap-4">
      <Campo id="dia" label="Dia" obrigatorio>
        <Select id="dia" value={dia} onChange={(e) => { setDia(e.target.value); setHora('') }}>
          {abertos.map((d) => (
            <option key={d.data} value={d.data}>
              {DIA_LABEL[d.dia_semana]} · {d.data.split('-').reverse().join('/')}
            </option>
          ))}
        </Select>
      </Campo>

      <Campo id="hora" label="Horário" obrigatorio>
        <Select id="hora" value={hora} onChange={(e) => setHora(e.target.value)}>
          <option value="">Selecione…</option>
          {horasDoDia.map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </Select>
      </Campo>

      <Campo id="servico" label="Serviço" obrigatorio>
        <Select id="servico" value={servicoId} onChange={(e) => setServicoId(e.target.value)}>
          <option value="">Selecione…</option>
          {servicos?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nome} (até {s.capacidade_padrao})
            </option>
          ))}
        </Select>
      </Campo>

      <Campo id="instrutor" label="Instrutor" obrigatorio>
        <Select
          id="instrutor"
          value={instrutorId}
          onChange={(e) => setInstrutorId(e.target.value)}
        >
          <option value="">Selecione…</option>
          {instrutores.map((i) => (
            <option key={i.id} value={i.id}>
              {i.nome}
            </option>
          ))}
        </Select>
      </Campo>

      <Campo id="capacidade" label="Capacidade (opcional)">
        <Input
          id="capacidade"
          type="number"
          min={1}
          placeholder="Herda a capacidade do serviço"
          value={capacidade}
          onChange={(e) => setCapacidade(e.target.value)}
        />
      </Campo>

      {erro && <Aviso>{erro}</Aviso>}

      <div className="mt-2 flex gap-3">
        <Button
          className="flex-1"
          disabled={!dia || !hora || !servicoId || !instrutorId}
          onClick={async () => {
            setErro(null)
            try {
              await criar.mutateAsync({
                service_id: Number(servicoId),
                professional_id: Number(instrutorId),
                // Sem sufixo de fuso: o backend interpreta no fuso do studio.
                inicia_em: `${dia}T${hora}:00`,
                capacidade: capacidade ? Number(capacidade) : null,
              })
              onPronto()
            } catch (e) {
              const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data
                ?.detail
              setErro(typeof d === 'string' ? d : 'Não foi possível criar a turma.')
            }
          }}
        >
          Criar turma
        </Button>
        <Button variante="secundario" className="flex-1" onClick={onPronto}>
          Cancelar
        </Button>
      </div>
    </div>
  )
}
