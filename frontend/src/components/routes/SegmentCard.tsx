import { ArrowRight, Trash2 } from 'lucide-react'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Card } from '../ui/card'

export interface SegmentCardProps {
  /**
   * Station name
   */
  stationName: string

  /**
   * Line name (optional - null for destination segments)
   */
  lineName?: string | null

  /**
   * Line color (hex code, optional - null for destination segments)
   */
  lineColor?: string | null

  /**
   * Segment sequence number
   */
  sequence: number

  /**
   * Whether this is the last segment
   */
  isLast: boolean

  /**
   * Whether delete button should be disabled
   */
  canDelete: boolean

  /**
   * Callback when delete button is clicked
   */
  onDelete: () => void
}

/**
 * Display a single segment in the route path
 *
 * Shows station name, line indicator with color, and optional delete button.
 * Displays an arrow to indicate connection to next segment (unless it's the last one).
 *
 * @example
 * <SegmentCard
 *   stationName="King's Cross"
 *   lineName="Northern"
 *   lineColor="#000000"
 *   sequence={0}
 *   isLast={false}
 *   canDelete={true}
 *   onDelete={() => handleDelete(0)}
 * />
 */
export function SegmentCard({
  stationName,
  lineName,
  lineColor,
  sequence,
  isLast,
  canDelete,
  onDelete,
}: SegmentCardProps) {
  const isDestination = !lineName || !lineColor

  return (
    <div className="flex items-center gap-2">
      <Card className="flex flex-1 items-center gap-3 p-3">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-sm font-medium">
          {sequence + 1}
        </div>
        <div className="flex-1">
          <div className="font-medium">{stationName}</div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {isDestination ? (
              <span>Destination</span>
            ) : (
              <>
                <Badge
                  style={{ backgroundColor: lineColor ?? undefined }}
                  className="h-3 w-3 rounded-full p-0"
                  aria-label={`${lineName} line color`}
                />
                <span>{lineName} line</span>
              </>
            )}
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          disabled={!canDelete}
          aria-label={`Delete segment ${sequence + 1}`}
          className="h-8 w-8"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </Card>

      {!isLast && (
        <ArrowRight className="h-5 w-5 flex-shrink-0 text-muted-foreground" aria-hidden="true" />
      )}
    </div>
  )
}
