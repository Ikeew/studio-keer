import { EmDesenvolvimento } from '@/components/ui/EmDesenvolvimento'
import { PageHeader } from '@/components/ui/PageHeader'

export function Pacientes() {
  return (
    <>
      <PageHeader title="Pacientes" subtitle="Gerencie o cadastro de pacientes" />
      <EmDesenvolvimento
        fase="Fase 2"
        descricao="Cadastro, busca e ficha do paciente."
      />
    </>
  )
}
