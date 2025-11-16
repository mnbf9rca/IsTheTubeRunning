import { useMemo } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'

/**
 * Hook to check if the current user has admin privileges
 *
 * This hook leverages the existing BackendAuthContext to determine admin status
 * based on the is_admin field returned from the /auth/me endpoint.
 *
 * It also handles the race condition where Auth0 finishes loading before backend
 * validation completes, preventing premature redirects on page refresh.
 *
 * @returns Object containing admin status, loading states, and user data
 *
 * @example
 * ```tsx
 * function AdminPanel() {
 *   const { isAdmin, isLoading, isInitializing } = useAdminCheck()
 *
 *   if (isLoading || isInitializing) return <Spinner />
 *   if (!isAdmin) return <Forbidden />
 *
 *   return <AdminDashboard />
 * }
 * ```
 */
export function useAdminCheck() {
  const { isAuthenticated, isLoading: auth0IsLoading } = useAuth()
  const { user, isBackendAuthenticated, isValidating } = useBackendAuth()

  const isAdmin = useMemo(() => {
    return isBackendAuthenticated && user?.is_admin === true
  }, [isBackendAuthenticated, user?.is_admin])

  // Detect initialization state: Auth0 is authenticated but backend user not loaded yet
  // This prevents redirect on page refresh before backend validation completes
  const isInitializing = useMemo(() => {
    return isAuthenticated && !auth0IsLoading && !user && !isValidating
  }, [isAuthenticated, auth0IsLoading, user, isValidating])

  return {
    isAdmin,
    isLoading: isValidating,
    isInitializing,
    user,
  }
}
