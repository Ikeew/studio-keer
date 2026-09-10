/**
 * Validação de CPF pelos dígitos verificadores.
 *
 * Espelha `backend/app/core/cpf.py`. É conveniência para quem digita — a
 * validação que vale é a do servidor, porque a API é chamável direto.
 */
export function cpfValido(valor: string): boolean {
  const cpf = valor.replace(/\D/g, '')

  if (cpf.length !== 11) return false
  // Sequências de dígito repetido passam no cálculo, mas não são CPF válido.
  if (/^(\d)\1{10}$/.test(cpf)) return false

  for (const tamanho of [9, 10]) {
    let soma = 0
    for (let i = 0; i < tamanho; i++) {
      soma += Number(cpf[i]) * (tamanho + 1 - i)
    }
    let digito = (soma * 10) % 11
    if (digito === 10) digito = 0
    if (digito !== Number(cpf[tamanho])) return false
  }

  return true
}
