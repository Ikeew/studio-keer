import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { useAuth } from '@/auth/useAuth'
import { rotaInicial } from '@/auth/permissoes'
import { usePageTitle } from '@/hooks/usePageTitle'

const schema = z.object({
  email: z.string().min(1, 'Informe o e-mail').email('E-mail inválido'),
  senha: z.string().min(1, 'Informe a senha'),
})

type Campos = z.infer<typeof schema>

export function Login() {
  usePageTitle('Entrar')
  const { usuario, entrar } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [erro, setErro] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Campos>({ resolver: zodResolver(schema) })

  if (usuario) return <Navigate to={rotaInicial(usuario.papel)} replace />

  async function onSubmit(campos: Campos) {
    setErro(null)
    try {
      await entrar(campos.email, campos.senha)
      // Volta para onde a pessoa tentou ir antes de ser mandada ao login.
      const destino = (location.state as { de?: string } | null)?.de
      navigate(destino ?? '/', { replace: true })
    } catch {
      // Mensagem única de propósito: dizer "e-mail não existe" revelaria
      // quais endereços têm conta no sistema.
      setErro('E-mail ou senha inválidos.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand px-4">
      <div className="w-full max-w-md rounded-card bg-surface p-8 shadow-card">
        <div className="mb-8">
          <h1 className="font-heading text-2xl font-semibold">Studio Keer</h1>
          <p className="mt-1 text-[15px] text-muted">Gestão de Agendamentos</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium">
              E-mail
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              autoFocus
              {...register('email')}
              className="w-full rounded-card border border-edge px-4 py-3 outline-none focus:border-brand"
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'erro-email' : undefined}
            />
            {errors.email && (
              <p id="erro-email" className="mt-1 text-sm text-danger">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="senha" className="mb-1 block text-sm font-medium">
              Senha
            </label>
            <input
              id="senha"
              type="password"
              autoComplete="current-password"
              {...register('senha')}
              className="w-full rounded-card border border-edge px-4 py-3 outline-none focus:border-brand"
              aria-invalid={!!errors.senha}
              aria-describedby={errors.senha ? 'erro-senha' : undefined}
            />
            {errors.senha && (
              <p id="erro-senha" className="mt-1 text-sm text-danger">
                {errors.senha.message}
              </p>
            )}
          </div>

          {erro && (
            <p role="alert" className="rounded-card bg-badge-alerta px-4 py-3 text-sm">
              {erro}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 rounded-card bg-brand px-4 py-3 font-medium text-white transition-colors hover:bg-brand-dark disabled:opacity-60"
          >
            {isSubmitting ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        {/* Exigência do projeto: ninguém pode confundir os dados de
            demonstração com informação real de paciente. */}
        <p className="mt-6 rounded-card bg-subtle px-4 py-3 text-sm text-muted">
          <strong className="text-ink">Ambiente de demonstração.</strong> Os
          pacientes, agendamentos e valores deste sistema são{' '}
          <strong className="text-ink">fictícios</strong>, criados para
          avaliação acadêmica. Nenhum CPF é válido e nenhum telefone existe.
        </p>
      </div>
    </div>
  )
}
