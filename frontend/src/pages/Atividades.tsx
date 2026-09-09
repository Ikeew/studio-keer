import { EmDesenvolvimento } from '@/components/ui/EmDesenvolvimento'
import { PageHeader } from '@/components/ui/PageHeader'

export function Atividades() {
  return (
    <>
      <PageHeader title="Atividades & Serviços" subtitle="Gerencie os serviços oferecidos" />
      <EmDesenvolvimento
        fase="Fase 2"
        descricao="Serviços com duração, preço e capacidade editável por turma."
      />
    </>
  )
}
