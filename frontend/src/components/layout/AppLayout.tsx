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
          <div className="flex flex-col items-center gap-2 md:items-end">
            <p className="text-sm text-muted-foreground">Powered by TfL Open Data</p>
            <p className="text-xs text-muted-foreground/50">
              Build: {__BUILD_COMMIT__.substring(0, 7)}
            </p>
          </div>
        </div>
      </footer>
      <Toaster />
    </div>
  )
}
