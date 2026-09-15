import { Outlet } from 'react-router-dom'

import { Sidebar } from './Sidebar'

export function AppLayout() {
  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar />
      <main aria-label="Conteúdo principal" className="flex-1 overflow-x-auto px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
