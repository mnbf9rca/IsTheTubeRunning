import { TrainFront } from 'lucide-react'
import { SegmentCard } from './SegmentCard'
import type { SegmentResponse, LineResponse, StationResponse } from '../../lib/api'

export interface SegmentListProps {
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

  /**
   * Whether the route is complete (has destination)
   * When true, delete buttons are disabled
   */
  isRouteComplete: boolean

  /**
   * Callback when a segment is deleted
   */
  onDeleteSegment: (sequence: number) => void
}

/**
 * Display an ordered list of route segments
 *
 * Shows the complete route path from start to end, with station names,
 * line indicators, and delete buttons for each segment.
 *
 * @example
 * <SegmentList
 *   segments={route.segments}
 *   lines={lines}
 *   stations={stations}
 *   onDeleteSegment={handleDelete}
 * />
 */
export function SegmentList({
  segments,
  lines,
  stations,
  isRouteComplete,
  onDeleteSegment,
}: SegmentListProps) {
  if (segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
        <TrainFront className="mb-4 h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h3 className="mb-2 text-lg font-semibold">No segments yet</h3>
        <p className="text-sm text-muted-foreground">
          Add your first station to start building your route.
        </p>
      </div>
    )
  }

  // Can only delete when route is NOT complete (editing mode)
  // User can delete down to 0 segments if they want
  const canDelete = !isRouteComplete

  return (
    <div className="space-y-2">
      {segments
        .sort((a, b) => a.sequence - b.sequence)
        .map((segment, index) => {
          // Find line and station details
          const line = segment.line_tfl_id
            ? lines.find((l) => l.tfl_id === segment.line_tfl_id)
            : null
          const station = stations.find((s) => s.tfl_id === segment.station_tfl_id)

          if (!station) {
            // Skip if station not found (shouldn't happen)
            return null
          }

          return (
            <SegmentCard
              key={segment.id}
              stationName={station.name}
              lineName={line?.name ?? null}
              lineColor={line?.color ?? null}
              sequence={segment.sequence}
              isLast={index === segments.length - 1}
              canDelete={canDelete}
              onDelete={() => onDeleteSegment(segment.sequence)}
            />
          )
        })}
    </div>
  )
}
