import { AlertCircle, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface ServiceUnavailableProps {
  onRetry: () => void
  lastChecked?: Date
  isRetrying?: boolean
}

export function ServiceUnavailable({
  onRetry,
  lastChecked,
  isRetrying = false,
}: ServiceUnavailableProps) {
  const [secondsSinceCheck, setSecondsSinceCheck] = useState(0)

  useEffect(() => {
    if (!lastChecked) return

    const interval = setInterval(() => {
      const seconds = Math.floor((Date.now() - lastChecked.getTime()) / 1000)
      setSecondsSinceCheck(seconds)
    }, 1000)

    return () => clearInterval(interval)
  }, [lastChecked])

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40 p-4">
      <Card className="max-w-lg w-full">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <AlertCircle className="h-16 w-16 text-destructive" />
          </div>
          <CardTitle className="text-2xl">Service Temporarily Unavailable</CardTitle>
          <CardDescription>
            We're having trouble connecting to our backend services. Please try again in a moment.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Connection Error</AlertTitle>
            <AlertDescription>
              The authentication system is currently unavailable. This may be due to maintenance or
              a temporary network issue.
            </AlertDescription>
          </Alert>

          {lastChecked && (
            <p className="text-sm text-muted-foreground text-center">
              Last checked: {secondsSinceCheck === 0 ? 'just now' : `${secondsSinceCheck}s ago`}
            </p>
          )}

          <Button onClick={onRetry} disabled={isRetrying} className="w-full" size="lg">
            {isRetrying ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry Now
              </>
            )}
          </Button>

          <p className="text-xs text-muted-foreground text-center">
            The system will automatically retry every 10 seconds
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
