import { EmDesenvolvimento } from '@/components/ui/EmDesenvolvimento'
import { PageHeader } from '@/components/ui/PageHeader'

export function Agenda() {
  return (
    <>
      <PageHeader title="Agendamentos" subtitle="Visualização semanal" />
      <EmDesenvolvimento
        fase="Fase 3"
        descricao="Grade semanal com horários, vagas por turma e instrutor responsável."
      />
    </>
  )
}
