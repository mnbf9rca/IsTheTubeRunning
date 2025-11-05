import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'

export default function Callback() {
  const { isLoading: auth0IsLoading, error: authError, logout } = useAuth()
  const { isBackendAuthenticated, isValidating, error: backendError } = useBackendAuth()
  const navigate = useNavigate()
  const [shouldShowError, setShouldShowError] = useState(false)

  useEffect(() => {
    let isMounted = true
    let timeoutId: NodeJS.Timeout

    // If backend authentication succeeds, redirect to dashboard
    if (isBackendAuthenticated) {
      navigate('/dashboard')
      return
    }

    // If backend validation fails, show error and logout
    if (!isValidating && !auth0IsLoading && backendError) {
      setShouldShowError(true)
      console.error('Backend validation error:', backendError)

      timeoutId = setTimeout(() => {
        if (isMounted) {
          logout({ logoutParams: { returnTo: window.location.origin + '/login' } })
        }
      }, 2000)
    }

    // If Auth0 authentication fails, logout immediately
    if (!auth0IsLoading && authError) {
      console.error('Auth0 error:', authError)
      logout({ logoutParams: { returnTo: window.location.origin + '/login' } })
    }

    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [
    isBackendAuthenticated,
    isValidating,
    backendError,
    auth0IsLoading,
    authError,
    navigate,
    logout,
  ])

  // Determine what message to show
  let message = 'Completing sign in...'
  if (shouldShowError && backendError) {
    message = 'Backend unavailable. Please ensure the server is running.'
  } else if (authError) {
    message = authError.message
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <div className="flex flex-col items-center space-y-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">{message}</p>
      </div>
    </div>
  )
}
