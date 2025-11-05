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
  forceLogout: () => Promise<void>
}

const BackendAuthContext = createContext<BackendAuthContextType | undefined>(undefined)

export function BackendAuthProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated: auth0IsAuthenticated, isLoading: auth0IsLoading, logout } = useAuth()
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  // Use ref to track validation state and prevent duplicate calls
  const validationRef = useRef({
    inProgress: false,
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

export function useBackendAuth() {
  const context = useContext(BackendAuthContext)
  if (context === undefined) {
    throw new Error('useBackendAuth must be used within a BackendAuthProvider')
  }
  return context
}
