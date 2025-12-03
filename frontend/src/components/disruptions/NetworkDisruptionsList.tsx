import { useDisruptions } from '@/hooks/useDisruptions'
import { DisruptionCard } from './DisruptionCard'
import { DisruptionSummary } from './DisruptionSummary'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { useEffect, useState } from 'react'

interface NetworkDisruptionsListProps {
  className?: string
}

/**
 * Displays all current TfL network disruptions with real-time polling
 *
 * Features:
 * - 10-second polling interval (per issue #227 requirements)
 * - Loading skeleton during initial fetch
 * - Error state with retry button
 * - "Good Service" summary for unaffected lines
 * - "Last updated" timestamp
 * - Responsive design (stacks on mobile)
 */
export function NetworkDisruptionsList({ className = '' }: NetworkDisruptionsListProps) {
  const { disruptions, loading, isRefreshing, error, refresh } = useDisruptions({
    pollInterval: 10000, // 10 seconds per issue requirements
    enabled: true,
    filterGoodService: true, // Filter out severity 10
  })

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Update timestamp when disruptions change
  useEffect(() => {
    if (disruptions && !loading) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLastUpdated(new Date())
    }
  }, [disruptions, loading])

  // Format last updated timestamp
  const formatTimestamp = (date: Date | null): string => {
    if (!date) return ''

    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins === 0) return 'just now'
    if (diffMins === 1) return '1 minute ago'
    if (diffMins < 60) return `${diffMins} minutes ago`
    return date.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // Loading skeleton - show 3 placeholder cards
  if (loading) {
    return (
      <section className={`space-y-4 ${className}`} aria-busy="true">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Current TfL Service Status</h2>
        </div>
        <div className="space-y-3" role="status" aria-label="Loading disruptions">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4">
                <div className="h-6 bg-muted rounded w-1/3 mb-2" />
                <div className="h-4 bg-muted rounded w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    )
  }

  // Error state - show error message and retry button
  if (error) {
    return (
      <section className={`space-y-4 ${className}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Current TfL Service Status</h2>
        </div>
        <Card className="border-destructive">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <AlertCircle className="h-6 w-6 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1 space-y-2">
                <p className="font-semibold text-destructive">Unable to load service status</p>
                <p className="text-sm text-muted-foreground">
                  {error.message ||
                    'There was a problem fetching TfL disruptions. Please try again.'}
                </p>
                <Button variant="outline" size="sm" onClick={refresh} className="mt-2">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Retry
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    )
  }

  // No disruptions (empty state) - show "Good service" summary only
  if (!disruptions || disruptions.length === 0) {
    return (
      <section className={`space-y-4 ${className}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Current TfL Service Status</h2>
          {lastUpdated && (
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              Last updated: {formatTimestamp(lastUpdated)}
              {isRefreshing && (
                <RefreshCw className="h-3 w-3 animate-spin" aria-label="Refreshing" />
              )}
            </p>
          )}
        </div>
        <DisruptionSummary disruptions={[]} />
      </section>
    )
  }

  // Main content - show disruptions and good service summary
  return (
    <section className={`space-y-4 ${className}`}>
      {/* Header with timestamp */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Current TfL Service Status</h2>
        {lastUpdated && (
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            Last updated: {formatTimestamp(lastUpdated)}
            {isRefreshing && <RefreshCw className="h-3 w-3 animate-spin" aria-label="Refreshing" />}
          </p>
        )}
      </div>

      {/* Disruption cards */}
      <div className="space-y-3" role="list">
        {disruptions.map((disruption) => (
          <DisruptionCard
            key={`${disruption.line_id}-${disruption.status_severity}-${disruption.created_at ?? ''}`}
            disruption={disruption}
          />
        ))}
      </div>

      {/* Good service summary */}
      <DisruptionSummary disruptions={disruptions} />
    </section>
  )
}
