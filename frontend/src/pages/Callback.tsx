import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function Callback() {
  const { isAuthenticated, isLoading, error } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isLoading) {
      if (isAuthenticated) {
        // Successfully authenticated, redirect to dashboard
        navigate('/dashboard')
      } else if (error) {
        // Authentication failed, redirect to login
        console.error('Authentication error:', error)
        navigate('/login')
      }
    }
  }, [isLoading, isAuthenticated, error, navigate])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <div className="flex flex-col items-center space-y-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-muted-foreground">
          {error ? 'Authentication failed. Redirecting...' : 'Completing sign in...'}
        </p>
      </div>
    </div>
  )
}
