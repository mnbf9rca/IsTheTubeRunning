import { TrainFront, ArrowRight } from 'lucide-react'
import { Badge } from '../ui/badge'
import { Card } from '../ui/card'
import type { SegmentResponse, LineResponse, StationResponse } from '../../lib/api'

export interface SegmentDisplayProps {
  /**
   * Array of segments to display
   */
  segments: SegmentResponse[]

  /**
   * Array of all lines (for looking up line details)
   */
  lines: LineResponse[]

  /**
   * Array of all stations (for looking up station details)
   */
  stations: StationResponse[]
}

/**
 * Display a read-only ordered list of route segments
 *
 * Shows the complete route path from start to end, with station names
 * and line indicators. This is the read-only version without delete buttons.
 *
 * @example
 * <SegmentDisplay
 *   segments={route.segments}
 *   lines={lines}
 *   stations={stations}
 * />
 */
export function SegmentDisplay({ segments, lines, stations }: SegmentDisplayProps) {
  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <TrainFront className="mb-3 h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">No journey segments defined yet.</p>
      </div>
    )
  }

  const sortedSegments = [...segments].sort((a, b) => a.sequence - b.sequence)

  return (
    <div className="space-y-2">
      {sortedSegments.map((segment, index) => {
        // Find line and station details
        const line = segment.line_tfl_id
          ? lines.find((l) => l.tfl_id === segment.line_tfl_id)
          : null
        const station = stations.find((s) => s.tfl_id === segment.station_tfl_id)

        if (!station) {
          // Skip if station not found (shouldn't happen)
          return null
        }

        const isLast = index === sortedSegments.length - 1
        const isDestination = !segment.line_tfl_id // NULL line_tfl_id means destination

        return (
          <div key={segment.id} className="flex items-center gap-2">
            <Card className="flex flex-1 items-center gap-3 p-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-sm font-medium">
                {segment.sequence + 1}
              </div>
              <div className="flex-1">
                <div className="font-medium">{station.name}</div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  {isDestination ? (
                    <span>Destination</span>
                  ) : line ? (
                    <>
                      <Badge
                        style={{ backgroundColor: line.color }}
                        className="h-3 w-3 rounded-full p-0"
                        aria-label={`${line.name} line color`}
                      />
                      <span>{line.name} line</span>
                    </>
                  ) : (
                    <span>Unknown line</span>
                  )}
                </div>
              </div>
            </Card>

            {!isLast && (
              <ArrowRight
                className="h-5 w-5 flex-shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
