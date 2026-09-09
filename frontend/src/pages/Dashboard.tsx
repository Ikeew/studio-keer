import { PageHeader } from '@/components/ui/PageHeader'
import { ConnectionStatus } from '@/components/ui/ConnectionStatus'

export function Dashboard() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Visão geral do seu estúdio" />
      <ConnectionStatus />
    </>
  )
}
