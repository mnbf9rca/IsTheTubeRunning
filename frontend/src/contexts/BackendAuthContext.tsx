import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import type { ReactNode } from 'react'
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

  // Use ref to track validation state and prevent duplicate/infinite calls
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
    validationRef.current.hasAttempted = false
    validationRef.current.inProgress = false
  }, [])

  // Auto-validate when Auth0 authenticates
  useEffect(() => {
    // Only validate if:
    // - Auth0 says authenticated
    // - Not currently loading
    // - No user yet
    // - Haven't attempted validation yet (or retrying after clearAuth)
    // - No existing error (don't retry on error)
    if (
      auth0IsAuthenticated &&
      !auth0IsLoading &&
      !user &&
      !validationRef.current.hasAttempted &&
      !error
    ) {
      validateWithBackend().catch(() => {
        // Error already set in state
      })
    }
  }, [auth0IsAuthenticated, auth0IsLoading, user, error, validateWithBackend])

  // Clear backend auth when Auth0 logs out
  useEffect(() => {
    if (!auth0IsAuthenticated && !auth0IsLoading) {
      clearAuth()
    }
  }, [auth0IsAuthenticated, auth0IsLoading, clearAuth])

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
