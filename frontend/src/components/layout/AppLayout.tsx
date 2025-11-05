import type { ReactNode } from 'react'
import { Toaster } from 'sonner'
import { Header } from './Header'

interface AppLayoutProps {
  children: ReactNode
}

export const AppLayout = ({ children }: AppLayoutProps) => {
  const currentYear = new Date().getFullYear()

  return (
    <div className="relative flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <div className="container py-6">{children}</div>
      </main>
      <footer className="border-t py-6">
        <div className="container flex flex-col items-center justify-between gap-4 md:flex-row">
          <p className="text-sm text-muted-foreground">
            © {currentYear} TfL Alerts. Not affiliated with Transport for London.
          </p>
          <p className="text-sm text-muted-foreground">Powered by TfL Open Data</p>
        </div>
      </footer>
      <Toaster />
    </div>
  )
}
