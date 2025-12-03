import { type GroupedLineDisruptionResponse, type LineStatusInfo } from '@/types'
import { Card, CardContent } from '@/components/ui/card'
import { DisruptionBadge } from './DisruptionBadge'
import { getLineColor } from '@/lib/tfl-colors'

interface DisruptionCardProps {
  disruption: GroupedLineDisruptionResponse
  className?: string
}

/**
 * Escape special regex characters in a string
 * Prevents regex metacharacters like (, ), ., +, etc. from being interpreted as regex syntax
 */
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Remove redundant line name prefix from reason text
 * e.g., "Lioness Line: No service..." -> "No service..."
 */
function cleanReason(reason: string | null | undefined, lineName: string): string | null {
  if (!reason) return null

  // Try multiple patterns: "Line Name:", "Line Name Line:", or just "Line Name "
  const patterns = [
    `${lineName}:`,
    `${lineName} Line:`,
    `${lineName} line:`,
    new RegExp(`^${escapeRegExp(lineName)}\\s+`, 'i'), // Match line name followed by space(s)
  ]

  let cleaned = reason.trim()
  for (const pattern of patterns) {
    if (typeof pattern === 'string') {
      if (cleaned.startsWith(pattern)) {
        cleaned = cleaned.slice(pattern.length).trim()
        break // Stop after first successful match
      }
    } else {
      const newCleaned = cleaned.replace(pattern, '').trim()
      if (newCleaned !== cleaned) {
        cleaned = newCleaned
        break // Stop after first successful match
      }
    }
  }

  return cleaned || null
}

/**
 * Group statuses by their reason text (after cleaning)
 * Returns array of { reason: string | null, statuses: LineStatusInfo[] }
 */
function groupStatusesByReason(
  statuses: LineStatusInfo[],
  lineName: string
): Array<{ reason: string | null; statuses: LineStatusInfo[] }> {
  const groups = new Map<string, LineStatusInfo[]>()

  for (const status of statuses) {
    const cleanedReason = cleanReason(status.reason, lineName)
    const key = cleanedReason || '__no_reason__'

    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key)!.push(status)
  }

  return Array.from(groups.entries()).map(([reason, statuses]) => ({
    reason: reason === '__no_reason__' ? null : reason,
    statuses,
  }))
}

/**
 * Displays a single TfL line with all its current statuses (grouped by line)
 *
 * Features:
 * - Vertical line color strip on left edge (TfL-inspired design)
 * - Line name with multiple status badges (if multiple statuses exist)
 * - Statuses with identical reasons are grouped together
 * - Removes redundant line name prefix from reason text
 * - Statuses are sorted by severity (lower = more severe) from backend
 * - Accessible with ARIA labels
 */
export function DisruptionCard({ disruption, className = '' }: DisruptionCardProps) {
  const lineColor = getLineColor(disruption.line_id)

  // All London Overground lines use striped pattern (colour-white-colour)
  const isOverground = disruption.mode === 'overground'

  // Group statuses by their reason text (after cleaning line name prefix)
  const groupedStatuses = groupStatusesByReason(disruption.statuses, disruption.line_name)

  // Build accessible description for screen readers
  const statusDescriptions = groupedStatuses
    .map((group) => {
      const severities = group.statuses.map((s) => s.status_severity_description).join(', ')
      return `${severities}${group.reason ? `: ${group.reason}` : ''}`
    })
    .join('; ')
  const ariaLabel = `${disruption.line_name}: ${statusDescriptions}`

  return (
    <Card className={`relative overflow-hidden ${className}`} role="article" aria-label={ariaLabel}>
      {/* Vertical line color strip on left edge */}
      {isOverground ? (
        // Overground: Three equal vertical stripes (colour-white-colour)
        <div className="absolute left-0 top-0 bottom-0 w-3 flex flex-row" aria-hidden="true">
          <div className="flex-1" style={{ backgroundColor: lineColor }} />
          <div className="flex-1 bg-white" />
          <div className="flex-1" style={{ backgroundColor: lineColor }} />
        </div>
      ) : (
        // Tube/Elizabeth: Solid color strip
        <div
          className="absolute left-0 top-0 bottom-0 w-3"
          style={{ backgroundColor: lineColor }}
          aria-hidden="true"
        />
      )}

      <CardContent className="p-4 pl-6">
        {/* Line name */}
        <h3 className="font-semibold text-lg leading-tight mb-3">{disruption.line_name}</h3>

        {/* Grouped statuses (by reason) */}
        <div className="space-y-3">
          {groupedStatuses.map((group, groupIndex) => (
            <div key={groupIndex} className="flex flex-col gap-2">
              {/* All badges for this reason group */}
              <div className="flex flex-wrap gap-2">
                {group.statuses.map((status, statusIndex) => (
                  <DisruptionBadge
                    key={`${groupIndex}-${statusIndex}`}
                    severity={status.status_severity}
                    severityDescription={status.status_severity_description}
                  />
                ))}
              </div>
              {/* Reason text (shown once for all statuses in this group) */}
              {group.reason && (
                <p className="text-sm text-muted-foreground leading-relaxed">{group.reason}</p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
