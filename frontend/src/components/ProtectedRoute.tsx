import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'

interface ProtectedRouteProps {
  children: ReactNode
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
  const { isLoading: auth0IsLoading } = useAuth()
  const { isBackendAuthenticated, isValidating } = useBackendAuth()

  // Show loading while Auth0 or backend validation is in progress
  if (auth0IsLoading || isValidating) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-muted-foreground">Authenticating...</p>
        </div>
      </div>
    )
  }

  // Only allow access if backend says user is authenticated
  if (!isBackendAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
