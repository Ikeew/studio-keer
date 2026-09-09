import { EmDesenvolvimento } from '@/components/ui/EmDesenvolvimento'
import { PageHeader } from '@/components/ui/PageHeader'

export function Financeiro() {
  return (
    <>
      <PageHeader title="Financeiro" subtitle="Controle de pagamentos mensais" />
      <EmDesenvolvimento
        fase="Fase 5"
        descricao="Mensalidades por matrícula, cobranças avulsas e baixa de pagamento."
      />
    </>
  )
}
