import { useMemo } from 'react'
import { useBackendAuth } from '@/contexts/BackendAuthContext'

/**
 * Hook to check if the current user has admin privileges
 *
 * This hook leverages the existing BackendAuthContext to determine admin status
 * based on the is_admin field returned from the /auth/me endpoint.
 *
 * @returns Object containing admin status and loading state
 *
 * @example
 * ```tsx
 * function AdminPanel() {
 *   const { isAdmin, isLoading } = useAdminCheck()
 *
 *   if (isLoading) return <Spinner />
 *   if (!isAdmin) return <Forbidden />
 *
 *   return <AdminDashboard />
 * }
 * ```
 */
export function useAdminCheck() {
  const { user, isBackendAuthenticated, isValidating } = useBackendAuth()

  const isAdmin = useMemo(() => {
    return isBackendAuthenticated && user?.is_admin === true
  }, [isBackendAuthenticated, user?.is_admin])

  return {
    isAdmin,
    isLoading: isValidating,
    user,
  }
}
