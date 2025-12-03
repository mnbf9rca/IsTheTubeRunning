import type { DisruptionResponse } from '@/types'
import { cn } from '@/lib/utils'

export interface DisruptionSummaryProps {
  /** Array of disruptions (all disruptions, not filtered) */
  disruptions: DisruptionResponse[]
  /** Additional CSS classes */
  className?: string
}

/**
 * Generate "Good service" summary message
 *
 * Shows "Good service on all lines" when there are no disruptions,
 * or "Good service on all other lines" when there are some disruptions.
 */
function generateSummaryMessage(disruptions: DisruptionResponse[]): string | null {
  if (disruptions.length === 0) {
    return 'Good service on all lines'
  }
  return 'Good service on all other lines'
}

/**
 * DisruptionSummary component
 *
 * Displays "Good service" summary message.
 * This provides context about the overall network status.
 *
 * @example
 * // With some disruptions
 * <DisruptionSummary disruptions={disruptions} />
 * // Output: "Good service on all other lines"
 *
 * // With no disruptions
 * <DisruptionSummary disruptions={[]} />
 * // Output: "Good service on all lines"
 */
export function DisruptionSummary({ disruptions, className }: DisruptionSummaryProps) {
  const message = generateSummaryMessage(disruptions)

  if (!message) {
    return null
  }

  return (
    <div className={cn('text-sm text-muted-foreground', className)} role="status">
      {message}
    </div>
  )
}
