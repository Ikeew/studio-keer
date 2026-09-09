export const PAPEIS = ['admin', 'recepcao', 'instrutor'] as const

export type Papel = (typeof PAPEIS)[number]

export type Usuario = {
  id: number
  nome: string
  email: string
  papel: Papel
  ativo: boolean
}

export type LoginResponse = {
  access_token: string
  token_type: string
  expires_in: number
  usuario: Usuario
}

/** Rótulos exibidos na interface. */
export const PAPEL_LABEL: Record<Papel, string> = {
  admin: 'Proprietária',
  recepcao: 'Recepção',
  instrutor: 'Instrutor',
}
