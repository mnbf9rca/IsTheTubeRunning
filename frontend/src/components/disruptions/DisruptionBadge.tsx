import { Badge } from '@/components/ui/badge'
import type { BadgeProps } from '@/components/ui/badge'

export interface DisruptionBadgeProps {
  /** TfL severity code (1-20, where 10 = Good Service) */
  severity: number
  /** Severity description from TfL */
  severityDescription?: string
  /** Compact mode (icon only) */
  compact?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * Map TfL severity code to badge variant
 *
 * TfL Severity codes:
 * - 1-4: Severe disruptions (closures, suspensions)
 * - 5-9: Minor/moderate delays
 * - 10: Good Service
 * - 11-20: Severe delays, reduced service, etc.
 *
 * Badge variants:
 * - destructive: Severe disruptions (red)
 * - outline: Minor/moderate delays (yellow/warning)
 * - secondary: Good service (green/neutral)
 */
function getSeverityVariant(severity: number): BadgeProps['variant'] {
  if (severity === 10) {
    return 'secondary' // Good Service
  } else if (severity >= 5 && severity <= 9) {
    return 'outline' // Minor/moderate delays
  } else {
    return 'destructive' // Severe disruptions
  }
}

/**
 * Get ARIA label for severity
 */
function getSeverityLabel(severity: number, description?: string): string {
  if (description) {
    return description
  }

  if (severity === 10) {
    return 'Good Service'
  } else if (severity >= 5 && severity <= 9) {
    return 'Minor Delays'
  } else {
    return 'Severe Disruption'
  }
}

/**
 * DisruptionBadge component
 *
 * Displays a severity indicator for TfL disruptions using color-coded badges.
 * Maps TfL severity codes to accessible badge variants.
 *
 * @example
 * <DisruptionBadge severity={10} severityDescription="Good Service" />
 * <DisruptionBadge severity={6} severityDescription="Minor Delays" compact />
 * <DisruptionBadge severity={20} severityDescription="Severe Delays" />
 */
export function DisruptionBadge({
  severity,
  severityDescription,
  compact = false,
  className,
}: DisruptionBadgeProps) {
  const variant = getSeverityVariant(severity)
  const label = getSeverityLabel(severity, severityDescription)

  if (compact) {
    // Compact mode: just a colored dot or minimal indicator
    return (
      <Badge variant={variant} className={className} aria-label={label} role="status">
        •
      </Badge>
    )
  }

  // Full mode: show severity description
  return (
    <Badge variant={variant} className={className} aria-label={label} role="status">
      {severityDescription || label}
    </Badge>
  )
}
