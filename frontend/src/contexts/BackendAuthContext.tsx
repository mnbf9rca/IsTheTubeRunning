import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { getCurrentUser, type UserResponse } from '@/lib/api'

interface BackendAuthContextType {
  user: UserResponse | null
  isBackendAuthenticated: boolean
  isValidating: boolean
  error: Error | null
  validateWithBackend: () => Promise<void>
  clearAuth: () => void
}

const BackendAuthContext = createContext<BackendAuthContextType | undefined>(undefined)

export function BackendAuthProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated: auth0IsAuthenticated, isLoading: auth0IsLoading } = useAuth()
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const validateWithBackend = useCallback(async () => {
    if (!auth0IsAuthenticated || auth0IsLoading) {
      return
    }

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
    }
  }, [auth0IsAuthenticated, auth0IsLoading])

  const clearAuth = useCallback(() => {
    setUser(null)
    setError(null)
  }, [])

  // Auto-validate when Auth0 authenticates
  useEffect(() => {
    // Only validate if:
    // - Auth0 says authenticated
    // - Not currently loading
    // - No user yet
    // - Not currently validating
    // - No existing error (don't retry on error)
    if (auth0IsAuthenticated && !auth0IsLoading && !user && !isValidating && !error) {
      validateWithBackend().catch(() => {
        // Error already set in state
      })
    }
  }, [auth0IsAuthenticated, auth0IsLoading, user, isValidating, error, validateWithBackend])

  return (
    <BackendAuthContext.Provider
      value={{
        user,
        isBackendAuthenticated: user !== null,
        isValidating,
        error,
        validateWithBackend,
        clearAuth,
      }}
    >
      {children}
    </BackendAuthContext.Provider>
  )
}

export function useBackendAuth() {
  const context = useContext(BackendAuthContext)
  if (context === undefined) {
    throw new Error('useBackendAuth must be used within a BackendAuthProvider')
  }
  return context
}
