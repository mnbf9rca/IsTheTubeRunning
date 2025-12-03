import type { DisruptionResponse } from '@/types'
import { cn } from '@/lib/utils'

export interface DisruptionSummaryProps {
  /** Array of disruptions (all disruptions, not filtered) */
  disruptions: DisruptionResponse[]
  /** Additional CSS classes */
  className?: string
}

/**
 * Get the list of modes represented in disruptions
 */
function getDisruptedModes(disruptions: DisruptionResponse[]): Set<string> {
  return new Set(disruptions.map((d) => d.mode))
}

/**
 * Generate "Good service" summary message
 *
 * Shows "Good service on all other tube, DLR and Elizabeth line routes"
 * when not all lines are disrupted.
 */
function generateSummaryMessage(disruptions: DisruptionResponse[]): string | null {
  if (disruptions.length === 0) {
    return 'Good service on all tube, DLR, Overground and Elizabeth line routes'
  }

  const disruptedModes = getDisruptedModes(disruptions)

  // If all major modes are disrupted, don't show summary
  // (this would be rare, but possible during major incidents)
  const hasAllModes =
    disruptedModes.has('tube') &&
    disruptedModes.has('dlr') &&
    disruptedModes.has('elizabeth-line') &&
    disruptedModes.has('overground')

  if (hasAllModes && disruptions.length > 10) {
    // If most lines are disrupted, don't show summary
    return null
  }

  // Show good service message for unaffected lines
  return 'Good service on all other tube, DLR, Overground and Elizabeth line routes'
}

/**
 * DisruptionSummary component
 *
 * Displays "Good service" summary message when not all lines are disrupted.
 * This provides context about the overall network status.
 *
 * @example
 * // With some disruptions
 * <DisruptionSummary disruptions={disruptions} />
 * // Output: "Good service on all other tube, DLR and Elizabeth line routes"
 *
 * // With no disruptions
 * <DisruptionSummary disruptions={[]} />
 * // Output: "Good service on all tube, DLR and Elizabeth line routes"
 *
 * // With major incident (all modes disrupted)
 * <DisruptionSummary disruptions={manyDisruptions} />
 * // Output: null (no summary shown)
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
