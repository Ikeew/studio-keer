import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useAtualizarServico, useCriarServico } from '@/api/servicos'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import { MODELOS_COBRANCA, MODELO_COBRANCA_LABEL, type Servico } from '@/types/servico'

const opcional = (v: unknown) => (v === '' || v === null ? undefined : Number(v))

const schema = z
  .object({
    nome: z.string().trim().min(2, 'Informe o nome'),
    duracao_min: z.coerce.number().int().positive('Duração deve ser maior que zero'),
    preco_reais: z.coerce.number().min(0, 'Preço não pode ser negativo'),
    capacidade_padrao: z.coerce
      .number()
      .int()
      .positive('Capacidade deve ser pelo menos 1'),
    cor: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Cor inválida'),
    modelo_cobranca: z.enum(MODELOS_COBRANCA),
    sugestao_pacote_sessoes: z.preprocess(opcional, z.number().int().positive().optional()),
    sugestao_pacote_validade_dias: z.preprocess(
      opcional,
      z.number().int().positive().optional(),
    ),
    sugestao_pacote_valor_reais: z.preprocess(opcional, z.number().min(0).optional()),
  })
  .refine(
    (d) =>
      d.modelo_cobranca === 'pacote' ||
      (d.sugestao_pacote_sessoes === undefined &&
        d.sugestao_pacote_validade_dias === undefined &&
        d.sugestao_pacote_valor_reais === undefined),
    {
      message: 'Sugestão de pacote só se aplica a serviço vendido como pacote',
      path: ['modelo_cobranca'],
    },
  )

type Campos = z.infer<typeof schema>

type Props = {
  servico?: Servico
  onPronto: () => void
}

export function ServicoForm({ servico, onPronto }: Props) {
  const [erro, setErro] = useState<string | null>(null)
  const criar = useCriarServico()
  const atualizar = useAtualizarServico(servico?.id ?? 0)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Campos>({
    resolver: zodResolver(schema),
    defaultValues: {
      nome: servico?.nome ?? '',
      duracao_min: servico?.duracao_min ?? 60,
      preco_reais: servico ? servico.preco_centavos / 100 : 0,
      capacidade_padrao: servico?.capacidade_padrao ?? 4,
      cor: servico?.cor ?? '#06B6D4',
      modelo_cobranca: servico?.modelo_cobranca ?? 'mensalidade',
      sugestao_pacote_sessoes: servico?.sugestao_pacote_sessoes ?? undefined,
      sugestao_pacote_validade_dias: servico?.sugestao_pacote_validade_dias ?? undefined,
      sugestao_pacote_valor_reais: servico?.sugestao_pacote_valor_centavos
        ? servico.sugestao_pacote_valor_centavos / 100
        : undefined,
    },
  })

  const ehPacote = watch('modelo_cobranca') === 'pacote'

  async function onSubmit(campos: Campos) {
    setErro(null)
    // Os campos de pacote são zerados quando o modelo não é pacote. Esconder
    // na tela não basta: o valor digitado antes da troca continuaria no form.
    const payload = {
      nome: campos.nome,
      duracao_min: campos.duracao_min,
      preco_centavos: Math.round(campos.preco_reais * 100),
      capacidade_padrao: campos.capacidade_padrao,
      cor: campos.cor,
      modelo_cobranca: campos.modelo_cobranca,
      sugestao_pacote_sessoes: ehPacote ? (campos.sugestao_pacote_sessoes ?? null) : null,
      sugestao_pacote_validade_dias: ehPacote
        ? (campos.sugestao_pacote_validade_dias ?? null)
        : null,
      sugestao_pacote_valor_centavos:
        ehPacote && campos.sugestao_pacote_valor_reais !== undefined
          ? Math.round(campos.sugestao_pacote_valor_reais * 100)
          : null,
    }

    try {
      if (servico) await atualizar.mutateAsync({ ...payload, ativo: servico.ativo })
      else await criar.mutateAsync(payload)
      onPronto()
    } catch (e) {
      const detalhe = (e as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail
      setErro(typeof detalhe === 'string' ? detalhe : 'Não foi possível salvar.')
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      <Campo id="nome" label="Nome da Atividade" obrigatorio erro={errors.nome?.message}>
        <Input id="nome" autoFocus placeholder="Ex: Pilates" {...register('nome')} />
      </Campo>

      <div className="grid grid-cols-2 gap-4">
        <Campo id="duracao_min" label="Duração (min)" obrigatorio erro={errors.duracao_min?.message}>
          <Input id="duracao_min" type="number" min={1} {...register('duracao_min')} />
        </Campo>
        <Campo id="preco_reais" label="Preço (R$)" obrigatorio erro={errors.preco_reais?.message}>
          <Input id="preco_reais" type="number" min={0} step="0.01" {...register('preco_reais')} />
        </Campo>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Campo
          id="capacidade_padrao"
          label="Capacidade da turma"
          obrigatorio
          erro={errors.capacidade_padrao?.message}
        >
          <Input id="capacidade_padrao" type="number" min={1} {...register('capacidade_padrao')} />
        </Campo>
        <Campo id="cor" label="Cor na agenda">
          <Input id="cor" type="color" className="h-[50px] p-1" {...register('cor')} />
        </Campo>
      </div>

      <Campo
        id="modelo_cobranca"
        label="Modelo de cobrança"
        obrigatorio
        erro={errors.modelo_cobranca?.message}
      >
        <Select id="modelo_cobranca" {...register('modelo_cobranca')}>
          {MODELOS_COBRANCA.map((m) => (
            <option key={m} value={m}>
              {MODELO_COBRANCA_LABEL[m]}
            </option>
          ))}
        </Select>
      </Campo>

      {ehPacote && (
        <fieldset className="rounded-card border border-edge p-4">
          <legend className="px-2 text-sm font-medium">Sugestão de pacote</legend>
          <p className="mb-4 text-sm text-muted">
            Só para pré-preencher a venda. Cada pacote é negociado no ato, e todos os
            campos ficam editáveis na hora.
          </p>
          <div className="grid grid-cols-3 gap-3">
            <Campo id="sugestao_pacote_sessoes" label="Sessões">
              <Input
                id="sugestao_pacote_sessoes"
                type="number"
                min={1}
                {...register('sugestao_pacote_sessoes')}
              />
            </Campo>
            <Campo id="sugestao_pacote_validade_dias" label="Validade (dias)">
              <Input
                id="sugestao_pacote_validade_dias"
                type="number"
                min={1}
                {...register('sugestao_pacote_validade_dias')}
              />
            </Campo>
            <Campo id="sugestao_pacote_valor_reais" label="Valor (R$)">
              <Input
                id="sugestao_pacote_valor_reais"
                type="number"
                min={0}
                step="0.01"
                {...register('sugestao_pacote_valor_reais')}
              />
            </Campo>
          </div>
        </fieldset>
      )}

      {erro && <Aviso>{erro}</Aviso>}

      <div className="mt-2 flex gap-3">
        <Button type="submit" disabled={isSubmitting} className="flex-1">
          {isSubmitting ? 'Salvando…' : servico ? 'Salvar' : 'Adicionar'}
        </Button>
        <Button type="button" variante="secundario" onClick={onPronto} className="flex-1">
          Cancelar
        </Button>
      </div>
    </form>
  )
}
