import { type GroupedLineDisruptionResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/card'
import { DisruptionBadge } from './DisruptionBadge'
import { getLineColor } from '@/lib/tfl-colors'

interface DisruptionCardProps {
  disruption: GroupedLineDisruptionResponse
  className?: string
}

/**
 * Displays a single TfL line with all its current statuses (grouped by line)
 *
 * Features:
 * - Vertical line color strip on left edge (TfL-inspired design)
 * - Line name with multiple status badges (if multiple statuses exist)
 * - Each status shows severity badge and optional reason
 * - Statuses are sorted by severity (lower = more severe) from backend
 * - Accessible with ARIA labels
 */
export function DisruptionCard({ disruption, className = '' }: DisruptionCardProps) {
  const lineColor = getLineColor(disruption.line_id)

  // Build accessible description for screen readers
  const statusDescriptions = disruption.statuses
    .map(
      (status) =>
        `${status.status_severity_description}${status.reason ? `: ${status.reason}` : ''}`
    )
    .join(', ')
  const ariaLabel = `${disruption.line_name}: ${statusDescriptions}`

  return (
    <Card className={`relative overflow-hidden ${className}`} role="article" aria-label={ariaLabel}>
      {/* Vertical line color strip on left edge (4px) */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ backgroundColor: lineColor }}
        aria-hidden="true"
      />

      <CardContent className="p-4 pl-6">
        {/* Line name */}
        <h3 className="font-semibold text-lg leading-tight mb-3">{disruption.line_name}</h3>

        {/* Multiple statuses (sorted by severity from backend) */}
        <div className="space-y-3">
          {disruption.statuses.map((status, index) => (
            <div key={index} className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <DisruptionBadge
                  severity={status.status_severity}
                  severityDescription={status.status_severity_description}
                />
                {/* Status reason/description */}
                {status.reason && (
                  <p className="text-sm text-muted-foreground leading-relaxed mt-2">
                    {status.reason}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
