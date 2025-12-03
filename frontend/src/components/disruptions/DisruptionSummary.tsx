import type { GroupedLineDisruptionResponse } from '@/types'
import { Card, CardContent } from '@/components/ui/card'
import { CheckCircle } from 'lucide-react'

export interface DisruptionSummaryProps {
  /** Array of grouped line disruptions (all disruptions, not filtered) */
  disruptions: GroupedLineDisruptionResponse[]
  /** Additional CSS classes */
  className?: string
}

/**
 * Generate "Good service" summary message
 *
 * Shows "Good service on all lines" when there are no disruptions,
 * or "Good service on all other lines" when there are some disruptions.
 */
function generateSummaryMessage(disruptions: GroupedLineDisruptionResponse[]): string | null {
  if (disruptions.length === 0) {
    return 'Good service on all lines'
  }
  return 'Good service on all other lines'
}

/**
 * DisruptionSummary component
 *
 * Displays "Good service" summary message as a prominent card.
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
    <Card className={className} role="status">
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0" aria-hidden="true" />
          <p className="text-base font-medium">{message}</p>
        </div>
      </CardContent>
    </Card>
  )
}
