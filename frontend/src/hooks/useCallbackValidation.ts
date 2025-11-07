import { useState, useCallback, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '@/lib/api'

type ValidationState = 'idle' | 'validating' | 'success' | 'auth_denied' | 'server_error'

interface UseCallbackValidationOptions {
  validateWithBackend: () => Promise<void>
  forceLogout: () => void
}

export function useCallbackValidation({
  validateWithBackend,
  forceLogout,
}: UseCallbackValidationOptions) {
  const navigate = useNavigate()
  const [validationState, setValidationState] = useState<ValidationState>('idle')
  const [errorMessage, setErrorMessage] = useState<string>('')
  const logoutTimeoutRef = useRef<number | null>(null)

  const performValidation = useCallback(async () => {
    setValidationState('validating')

    try {
      await validateWithBackend()
      setValidationState('success')
      navigate('/dashboard')
    } catch (error) {
      // Determine error type
      if (error instanceof ApiError) {
        if (error.status === 401 || error.status === 403) {
          // Backend denies auth - force logout
          setValidationState('auth_denied')
          setErrorMessage('Authentication denied by server. Logging out...')
          console.error('Backend denied authentication:', error)

          // Force logout after a brief delay
          logoutTimeoutRef.current = setTimeout(() => {
            forceLogout()
          }, 2000)
        } else if (error.status >= 500) {
          // Server error - allow retry
          setValidationState('server_error')
          setErrorMessage(`Server error (${error.status}). Please try again.`)
          console.error('Backend server error:', error)
        } else {
          // Other error - treat as server error
          setValidationState('server_error')
          setErrorMessage(`Unexpected error: ${error.message}`)
          console.error('Backend validation error:', error)
        }
      } else {
        // Network error or other issue - allow retry
        setValidationState('server_error')
        setErrorMessage('Unable to connect to server. Please check your connection.')
        console.error('Backend validation failed:', error)
      }
    }
  }, [validateWithBackend, forceLogout, navigate])

  const handleRetry = useCallback(async () => {
    setValidationState('idle')
    setErrorMessage('')
    await performValidation()
  }, [performValidation])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (logoutTimeoutRef.current) {
        clearTimeout(logoutTimeoutRef.current)
      }
    }
  }, [])

  return {
    validationState,
    errorMessage,
    performValidation,
    handleRetry,
  }
}
