import { createContext, useState, useEffect, useCallback, useRef } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import type { UserResponse } from '@/types'
import { getCurrentUser } from '@/lib/api'

interface BackendAuthContextType {
  user: UserResponse | null
  isBackendAuthenticated: boolean
  isValidating: boolean
  error: Error | null
  validateWithBackend: () => Promise<void>
  clearAuth: () => void
  forceLogout: () => Promise<void>
}

const BackendAuthContext = createContext<BackendAuthContextType | undefined>(undefined)

// Export context for use in hooks
export { BackendAuthContext }

export function BackendAuthProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated: auth0IsAuthenticated, isLoading: auth0IsLoading, logout } = useAuth()
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  // Use ref to track validation state and prevent duplicate calls
  const validationRef = useRef({
    inProgress: false,
    hasAttempted: false,
  })

  const validateWithBackend = useCallback(async () => {
    if (!auth0IsAuthenticated || auth0IsLoading) {
      return
    }

    // Prevent concurrent validations
    if (validationRef.current.inProgress) {
      return
    }

    validationRef.current.inProgress = true
    validationRef.current.hasAttempted = true

    try {
      setIsValidating(true)
      setError(null)
      const userData = await getCurrentUser()
      setUser(userData)
    } catch (err) {
      setError(err as Error)
      setUser(null)
      throw err
    } finally {
      setIsValidating(false)
      validationRef.current.inProgress = false
    }
  }, [auth0IsAuthenticated, auth0IsLoading])

  const clearAuth = useCallback(() => {
    setUser(null)
    setError(null)
    validationRef.current.inProgress = false
    validationRef.current.hasAttempted = false
  }, [])

  const forceLogout = useCallback(async () => {
    // Clear backend state first
    clearAuth()

    // Then logout from Auth0
    await logout()
  }, [logout, clearAuth])

  // Clear backend auth when Auth0 logs out
  useEffect(() => {
    if (!auth0IsAuthenticated && !auth0IsLoading) {
      clearAuth()
    }
  }, [auth0IsAuthenticated, auth0IsLoading, clearAuth])

  // Automatic validation on Auth0 authentication (e.g., page refresh)
  // This ensures that when a user refreshes the page with valid Auth0 tokens,
  // we automatically validate with the backend
  useEffect(() => {
    // Only auto-validate if:
    // 1. Auth0 is authenticated and not loading
    // 2. We don't have a backend user yet
    // 3. We're not currently validating
    // 4. We haven't attempted validation yet (prevents retry loops on error)
    if (
      auth0IsAuthenticated &&
      !auth0IsLoading &&
      !user &&
      !isValidating &&
      !validationRef.current.hasAttempted
    ) {
      // Call validation but don't throw if it fails (just log)
      validateWithBackend().catch((err) => {
        console.error('Auto-validation failed:', err)
        // Error is already set in state by validateWithBackend
      })
    }
  }, [auth0IsAuthenticated, auth0IsLoading, user, isValidating, validateWithBackend])

  return (
    <BackendAuthContext.Provider
      value={{
        user,
        isBackendAuthenticated: user !== null,
        isValidating,
        error,
        validateWithBackend,
        clearAuth,
        forceLogout,
      }}
    >
      {children}
    </BackendAuthContext.Provider>
  )
}

// Re-export hook for backward compatibility
// eslint-disable-next-line react-refresh/only-export-components
export { useBackendAuth } from '@/hooks/useBackendAuth'
