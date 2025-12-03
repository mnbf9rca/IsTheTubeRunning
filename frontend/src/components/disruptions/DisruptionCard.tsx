import { type DisruptionResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/card'
import { DisruptionBadge } from './DisruptionBadge'
import { getLineColor } from '@/lib/tfl-colors'

interface DisruptionCardProps {
  disruption: DisruptionResponse
  className?: string
}

/**
 * Displays a single TfL disruption with line-specific branding
 *
 * Features:
 * - Vertical line color strip on left edge (TfL-inspired design)
 * - Line name and severity badge
 * - Optional disruption reason/description
 * - Accessible with ARIA labels
 */
export function DisruptionCard({ disruption, className = '' }: DisruptionCardProps) {
  const lineColor = getLineColor(disruption.line_id)

  // Build accessible description for screen readers
  const ariaLabel = `${disruption.line_name}: ${disruption.status_severity_description}${
    disruption.reason ? `. ${disruption.reason}` : ''
  }`

  return (
    <Card className={`relative overflow-hidden ${className}`} role="article" aria-label={ariaLabel}>
      {/* Vertical line color strip on left edge (4px) */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ backgroundColor: lineColor }}
        aria-hidden="true"
      />

      <CardContent className="p-4 pl-6">
        {/* Line name and severity badge */}
        <div className="flex items-start justify-between gap-4 mb-2">
          <h3 className="font-semibold text-lg leading-tight">{disruption.line_name}</h3>
          <DisruptionBadge
            severity={disruption.status_severity}
            severityDescription={disruption.status_severity_description}
          />
        </div>

        {/* Disruption reason/description */}
        {disruption.reason && (
          <p className="text-sm text-muted-foreground leading-relaxed">{disruption.reason}</p>
        )}
      </CardContent>
    </Card>
  )
}
