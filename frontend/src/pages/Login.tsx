import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { Train, Bell, MapPin, Shield } from 'lucide-react'

export default function Login() {
  const { isAuthenticated, login, isLoading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard')
    }
  }, [isAuthenticated, navigate])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-background to-muted p-4">
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">TfL Alerts</h1>
        <p className="mt-2 text-lg text-muted-foreground">Never miss a tube disruption again</p>
      </div>

      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Get Started</CardTitle>
          <CardDescription>
            Sign in to create routes and receive alerts about disruptions
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col items-center space-y-2 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <MapPin className="h-6 w-6 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">Create Routes</p>
            </div>
            <div className="flex flex-col items-center space-y-2 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <Bell className="h-6 w-6 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">Get Alerts</p>
            </div>
            <div className="flex flex-col items-center space-y-2 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <Train className="h-6 w-6 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">Live Updates</p>
            </div>
            <div className="flex flex-col items-center space-y-2 text-center">
              <div className="rounded-full bg-primary/10 p-3">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">Secure</p>
            </div>
          </div>

          <Button onClick={login} className="w-full" size="lg">
            Sign in with Auth0
          </Button>

          <p className="text-center text-xs text-muted-foreground">
            By signing in, you agree to receive notifications about transport disruptions
          </p>
        </CardContent>
      </Card>

      <p className="mt-8 text-sm text-muted-foreground">
        Powered by TfL Open Data • Not affiliated with Transport for London
      </p>
    </div>
  )
}
