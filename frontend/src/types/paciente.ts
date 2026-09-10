export const SEXOS = ['feminino', 'masculino', 'outro', 'nao_informado'] as const
export type Sexo = (typeof SEXOS)[number]

export const ESTADOS_CIVIS = [
  'solteiro',
  'casado',
  'divorciado',
  'viuvo',
  'uniao_estavel',
  'nao_informado',
] as const
export type EstadoCivil = (typeof ESTADOS_CIVIS)[number]

export const SEXO_LABEL: Record<Sexo, string> = {
  feminino: 'Feminino',
  masculino: 'Masculino',
  outro: 'Outro',
  nao_informado: 'Não informado',
}

export const ESTADO_CIVIL_LABEL: Record<EstadoCivil, string> = {
  solteiro: 'Solteiro(a)',
  casado: 'Casado(a)',
  divorciado: 'Divorciado(a)',
  viuvo: 'Viúvo(a)',
  uniao_estavel: 'União estável',
  nao_informado: 'Não informado',
}

export type Paciente = {
  id: number
  nome_completo: string
  cpf: string | null
  cpf_formatado: string | null
  data_nascimento: string | null
  idade: number | null
  sexo: Sexo
  estado_civil: EstadoCivil
  profissao: string | null
  email: string | null
  telefone: string | null
  emergencia_nome: string | null
  emergencia_telefone: string | null
  observacoes: string | null
  consentimento_lgpd: boolean
  consentimento_em: string | null
  ativo: boolean
}

export type PaginaDePacientes = {
  itens: Paciente[]
  total: number
  pagina: number
  tamanho: number
}
