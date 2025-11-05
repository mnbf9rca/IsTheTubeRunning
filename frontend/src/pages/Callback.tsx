import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'
import { ApiError } from '@/lib/api'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertCircle } from 'lucide-react'

export default function Callback() {
  const {
    isAuthenticated: auth0IsAuthenticated,
    isLoading: auth0IsLoading,
    error: authError,
  } = useAuth()
  const { isBackendAuthenticated, validateWithBackend, forceLogout } = useBackendAuth()
  const navigate = useNavigate()
  const [validationState, setValidationState] = useState<
    'idle' | 'validating' | 'success' | 'auth_denied' | 'server_error'
  >('idle')
  const [errorMessage, setErrorMessage] = useState<string>('')

  // Explicit validation on mount when Auth0 is ready
  useEffect(() => {
    let isMounted = true

    const performValidation = async () => {
      // Wait for Auth0 to finish loading
      if (auth0IsLoading) {
        return
      }

      // If Auth0 failed, redirect to login
      if (authError) {
        console.error('Auth0 error:', authError)
        setErrorMessage(`Authentication failed: ${authError.message}`)
        setValidationState('auth_denied')
        return
      }

      // If not authenticated with Auth0, redirect to login
      if (!auth0IsAuthenticated) {
        navigate('/login')
        return
      }

      // Already validated successfully
      if (isBackendAuthenticated) {
        navigate('/dashboard')
        return
      }

      // Perform explicit backend validation
      if (validationState === 'idle') {
        setValidationState('validating')

        try {
          await validateWithBackend()

          if (isMounted) {
            setValidationState('success')
            navigate('/dashboard')
          }
        } catch (error) {
          if (!isMounted) return

          // Determine error type
          if (error instanceof ApiError) {
            if (error.status === 401 || error.status === 403) {
              // Backend denies auth - force logout
              setValidationState('auth_denied')
              setErrorMessage('Authentication denied by server. Logging out...')
              console.error('Backend denied authentication:', error)

              // Force logout after a brief delay
              setTimeout(() => {
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
      }
    }

    performValidation()

    return () => {
      isMounted = false
    }
  }, [
    auth0IsAuthenticated,
    auth0IsLoading,
    authError,
    isBackendAuthenticated,
    validateWithBackend,
    forceLogout,
    navigate,
    validationState,
  ])

  const handleRetry = () => {
    setValidationState('idle')
    setErrorMessage('')
  }

  // Show error states
  if (validationState === 'auth_denied') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Authentication Failed</AlertTitle>
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        </div>
      </div>
    )
  }

  if (validationState === 'server_error') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Connection Error</AlertTitle>
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
          <div className="flex gap-2">
            <Button onClick={handleRetry} className="flex-1">
              Retry
            </Button>
            <Button onClick={() => navigate('/login')} variant="outline" className="flex-1">
              Back to Login
            </Button>
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <div className="flex flex-col items-center space-y-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">
          {validationState === 'validating' ? 'Verifying with server...' : 'Completing sign in...'}
        </p>
      </div>
    </div>
  )
}
