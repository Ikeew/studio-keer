import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { useAtualizarPaciente, useCriarPaciente } from '@/api/pacientes'
import { Aviso } from '@/components/ui/Aviso'
import { Button } from '@/components/ui/Button'
import { Campo, Input, Select } from '@/components/ui/Campo'
import { cpfValido } from '@/lib/cpf'
import { ESTADOS_CIVIS, ESTADO_CIVIL_LABEL, SEXOS, SEXO_LABEL } from '@/types/paciente'
import type { Paciente } from '@/types/paciente'

const vazioParaNulo = (v: unknown) => (v === '' ? null : v)

// Espelha o Pydantic do backend. A validação daqui é conveniência para quem
// digita; a que vale é a do servidor.
const schema = z.object({
  nome_completo: z.string().trim().min(3, 'Informe o nome completo'),
  cpf: z.preprocess(
    vazioParaNulo,
    z
      .string()
      .nullable()
      .refine((v) => !v || cpfValido(v), 'CPF inválido'),
  ),
  data_nascimento: z.preprocess(
    vazioParaNulo,
    z
      .string()
      .nullable()
      .refine(
        (v) => !v || v <= new Date().toISOString().slice(0, 10),
        'A data não pode estar no futuro',
      ),
  ),
  sexo: z.enum(SEXOS),
  estado_civil: z.enum(ESTADOS_CIVIS),
  profissao: z.preprocess(vazioParaNulo, z.string().nullable()),
  email: z.preprocess(vazioParaNulo, z.string().email('E-mail inválido').nullable()),
  telefone: z.preprocess(vazioParaNulo, z.string().nullable()),
  emergencia_nome: z.preprocess(vazioParaNulo, z.string().nullable()),
  emergencia_telefone: z.preprocess(vazioParaNulo, z.string().nullable()),
  consentimento_lgpd: z.boolean(),
})

type Campos = z.infer<typeof schema>

type Props = {
  paciente?: Paciente
  onPronto: () => void
}

export function PacienteForm({ paciente, onPronto }: Props) {
  const [erro, setErro] = useState<string | null>(null)
  const criar = useCriarPaciente()
  const atualizar = useAtualizarPaciente(paciente?.id ?? 0)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Campos>({
    resolver: zodResolver(schema),
    defaultValues: {
      nome_completo: paciente?.nome_completo ?? '',
      cpf: paciente?.cpf_formatado ?? null,
      data_nascimento: paciente?.data_nascimento ?? null,
      sexo: paciente?.sexo ?? 'nao_informado',
      estado_civil: paciente?.estado_civil ?? 'nao_informado',
      profissao: paciente?.profissao ?? null,
      email: paciente?.email ?? null,
      telefone: paciente?.telefone ?? null,
      emergencia_nome: paciente?.emergencia_nome ?? null,
      emergencia_telefone: paciente?.emergencia_telefone ?? null,
      consentimento_lgpd: paciente?.consentimento_lgpd ?? false,
    },
  })

  async function onSubmit(campos: Campos) {
    setErro(null)
    try {
      if (paciente) await atualizar.mutateAsync(campos)
      else await criar.mutateAsync(campos)
      onPronto()
    } catch (e) {
      const detalhe = (e as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail
      setErro(typeof detalhe === 'string' ? detalhe : 'Não foi possível salvar. Tente de novo.')
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
      <Campo id="nome_completo" label="Nome completo" obrigatorio erro={errors.nome_completo?.message}>
        <Input id="nome_completo" autoFocus {...register('nome_completo')} />
      </Campo>

      <div className="grid grid-cols-2 gap-4">
        <Campo id="cpf" label="CPF" erro={errors.cpf?.message}>
          <Input id="cpf" placeholder="000.000.000-00" {...register('cpf')} />
        </Campo>
        <Campo id="data_nascimento" label="Nascimento" erro={errors.data_nascimento?.message}>
          <Input id="data_nascimento" type="date" {...register('data_nascimento')} />
        </Campo>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Campo id="sexo" label="Sexo">
          <Select id="sexo" {...register('sexo')}>
            {SEXOS.map((s) => (
              <option key={s} value={s}>
                {SEXO_LABEL[s]}
              </option>
            ))}
          </Select>
        </Campo>
        <Campo id="estado_civil" label="Estado civil">
          <Select id="estado_civil" {...register('estado_civil')}>
            {ESTADOS_CIVIS.map((e) => (
              <option key={e} value={e}>
                {ESTADO_CIVIL_LABEL[e]}
              </option>
            ))}
          </Select>
        </Campo>
      </div>

      <Campo id="profissao" label="Profissão">
        <Input id="profissao" {...register('profissao')} />
      </Campo>

      <div className="grid grid-cols-2 gap-4">
        <Campo id="email" label="E-mail" erro={errors.email?.message}>
          <Input id="email" type="email" {...register('email')} />
        </Campo>
        <Campo id="telefone" label="Telefone">
          <Input id="telefone" placeholder="(11) 90000-0000" {...register('telefone')} />
        </Campo>
      </div>

      <fieldset className="rounded-card border border-edge p-4">
        <legend className="px-2 text-sm font-medium">Contato de emergência</legend>
        <div className="grid grid-cols-2 gap-4">
          <Campo id="emergencia_nome" label="Nome">
            <Input id="emergencia_nome" {...register('emergencia_nome')} />
          </Campo>
          <Campo id="emergencia_telefone" label="Telefone">
            <Input id="emergencia_telefone" {...register('emergencia_telefone')} />
          </Campo>
        </div>
      </fieldset>

      <label className="flex items-start gap-3 rounded-card bg-subtle p-4 text-[15px]">
        <input
          type="checkbox"
          {...register('consentimento_lgpd')}
          className="mt-1 h-4 w-4 accent-brand"
        />
        <span>
          O paciente autoriza o tratamento dos seus dados pessoais para fins de agendamento
          e cobrança <span className="text-muted">(LGPD)</span>.
        </span>
      </label>

      {erro && <Aviso>{erro}</Aviso>}

      <div className="mt-2 flex gap-3">
        <Button type="submit" disabled={isSubmitting} className="flex-1">
          {isSubmitting ? 'Salvando…' : paciente ? 'Salvar alterações' : 'Cadastrar'}
        </Button>
        <Button type="button" variante="secundario" onClick={onPronto} className="flex-1">
          Cancelar
        </Button>
      </div>
    </form>
  )
}
