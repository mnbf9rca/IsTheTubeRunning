import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'
import { useCallbackValidation } from '@/hooks/useCallbackValidation'
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

  const { validationState, errorMessage, performValidation, handleRetry } = useCallbackValidation({
    validateWithBackend,
    forceLogout,
  })

  // Explicit validation on mount when Auth0 is ready
  useEffect(() => {
    const checkAndValidate = async () => {
      // Wait for Auth0 to finish loading
      if (auth0IsLoading) {
        return
      }

      // If Auth0 failed, show error
      if (authError) {
        console.error('Auth0 error:', authError)
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

      // Perform explicit backend validation only once
      if (validationState === 'idle') {
        await performValidation()
      }
    }

    checkAndValidate()
  }, [
    auth0IsAuthenticated,
    auth0IsLoading,
    authError,
    isBackendAuthenticated,
    navigate,
    validationState,
    performValidation,
  ])

  // Show error states
  // Handle Auth0 errors
  if (authError) {
    // Detect "Invalid state" error (happens when state expires or is cleared)
    const isInvalidStateError =
      authError.message?.includes('Invalid state') || authError.message?.includes('state')

    if (isInvalidStateError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center p-4">
          <div className="max-w-md w-full space-y-4">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Session Expired</AlertTitle>
              <AlertDescription>
                Your login session expired. This can happen if you took too long on the login page
                or if your browser was closed during login.
              </AlertDescription>
            </Alert>
            <Button
              onClick={() => {
                // Clear any stale Auth0 state and redirect to login
                sessionStorage.clear()
                navigate('/login')
              }}
              className="w-full"
            >
              Try Logging In Again
            </Button>
          </div>
        </div>
      )
    }

    // Handle other Auth0 errors
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Authentication Failed</AlertTitle>
            <AlertDescription>Authentication failed: {authError.message}</AlertDescription>
          </Alert>
          <Button onClick={() => navigate('/login')} variant="outline" className="w-full">
            Back to Login
          </Button>
        </div>
      </div>
    )
  }

  // Handle backend validation errors
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
