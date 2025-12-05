import { CheckCircle } from 'lucide-react'
import { DisruptionBadge } from '@/components/disruptions'
import type { RouteDisruptionResponse } from '@/types'
import { cn } from '@/lib/utils'

export interface RouteDisruptionStatusProps {
  /** The disruption affecting this route (null = good service) */
  disruption: RouteDisruptionResponse | null
  /** Whether disruption data is still loading */
  loading?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * RouteDisruptionStatus component
 *
 * Displays the disruption status for a single route:
 * - Loading state: skeleton placeholder
 * - No disruption: "Good Service" with green checkmark
 * - Has disruption: Badge with severity and reason summary
 *
 * @example
 * <RouteDisruptionStatus disruption={routeDisruption} loading={false} />
 * <RouteDisruptionStatus disruption={null} />
 */
export function RouteDisruptionStatus({
  disruption,
  loading = false,
  className,
}: RouteDisruptionStatusProps) {
  // Loading state: show skeleton placeholder
  if (loading) {
    return (
      <div
        className={cn('flex items-center gap-2 h-6', className)}
        role="status"
        aria-label="Loading disruption status"
        aria-busy="true"
      >
        <div className="h-5 w-24 bg-muted animate-pulse rounded" />
      </div>
    )
  }

  // No disruption: show "Good Service"
  if (!disruption) {
    return (
      <div
        className={cn('flex items-center gap-2 text-sm text-muted-foreground', className)}
        role="status"
        aria-label="Good Service"
      >
        <CheckCircle className="h-4 w-4 text-green-600" aria-hidden="true" />
        <span>Good Service</span>
      </div>
    )
  }

  // Has disruption: show badge and reason
  const { disruption: disruptionData } = disruption
  const reason = disruptionData.reason
    ? disruptionData.reason.replace(new RegExp(`^${disruptionData.line_name}:\\s*`, 'i'), '')
    : null

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-center gap-2">
        <DisruptionBadge
          severity={disruptionData.status_severity}
          severityDescription={disruptionData.status_severity_description}
        />
        <span className="text-sm font-medium">{disruptionData.line_name}</span>
      </div>
      {reason && (
        <p className="text-xs text-muted-foreground line-clamp-2" title={reason}>
          {reason}
        </p>
      )}
    </div>
  )
}
