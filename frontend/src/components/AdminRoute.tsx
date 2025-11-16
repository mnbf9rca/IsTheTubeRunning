import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useAdminCheck } from '@/hooks/useAdminCheck'

interface AdminRouteProps {
  children: ReactNode
}

/**
 * Route guard component that restricts access to admin users only
 *
 * This component checks both authentication AND admin privileges.
 * Non-admin authenticated users are redirected to the dashboard with an error message.
 * Unauthenticated users are handled by the admin check logic.
 *
 * @example
 * ```tsx
 * <Route
 *   path="/admin/users"
 *   element={
 *     <AdminRoute>
 *       <AdminUsersPage />
 *     </AdminRoute>
 *   }
 * />
 * ```
 */
export const AdminRoute = ({ children }: AdminRouteProps) => {
  const { isLoading: auth0IsLoading } = useAuth()
  const { isAdmin, isLoading } = useAdminCheck()
  const location = useLocation()

  // Show loading while checking authentication and admin status
  if (auth0IsLoading || isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-muted-foreground">Checking permissions...</p>
        </div>
      </div>
    )
  }

  // Redirect to dashboard if not admin
  // Pass error message via state so dashboard can display it
  if (!isAdmin) {
    return (
      <Navigate
        to="/dashboard"
        state={{
          from: location.pathname,
          error: 'Admin privileges required to access this page',
        }}
        replace
      />
    )
  }

  return <>{children}</>
}
