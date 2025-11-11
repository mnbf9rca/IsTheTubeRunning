/**
 * Pure segment building functions for SegmentBuilder
 *
 * This module provides pure functions for building and manipulating route segments.
 * All functions are pure (no side effects, same input → same output) and return
 * new arrays rather than mutating inputs.
 *
 * These functions were extracted from SegmentBuilder.tsx to:
 * - Separate business logic from React state management
 * - Enable 100% test coverage on complex segment building algorithms
 * - Eliminate code duplication between handleContinueJourney and handleMarkAsDestination
 * - Make segment building logic reusable and composable
 *
 * @see ADR 11: Frontend State Management Pattern - Pure Function Architecture
 * @see Issue #96: Extract Segment Building Logic from SegmentBuilder
 */

import type { StationResponse, LineResponse } from '@/lib/api'
import type { SegmentRequest } from './types'
import { isStationLastInRoute } from './validation'
import { isSameLine } from './utils'

/**
 * Result of deleting a segment with truncation context
 */
export interface DeletionResult {
  /** Remaining segments after deletion (resequenced) */
  segments: SegmentRequest[]
  /**
   * Context for resuming route building after truncation
   *
   * Both fields are null when:
   * - Deleting from sequence 0 (clears all segments)
   * - Station/line lookup fails for remaining segments
   *
   * When null, UI should transition back to initial state (select-station)
   */
  resumeFrom: {
    /**
     * Station to resume from (from last remaining segment).
     * Null if no segments remain after deletion.
     */
    station: StationResponse | null
    /**
     * Line to resume on (from last remaining segment).
     * Null if no segments remain after deletion.
     */
    line: LineResponse | null
  }
}

/**
 * Parameters for building segments when continuing a journey
 */
export interface BuildContinueSegmentsParams {
  /** Current station user is at (may or may not be in route already) */
  currentStation: StationResponse
  /** Line user is currently on */
  selectedLine: LineResponse
  /** Next station user wants to travel to */
  nextStation: StationResponse
  /** Current route segments */
  currentSegments: SegmentRequest[]
  /** Line user wants to continue on (may be same or different from selectedLine) */
  continueLine: LineResponse
}

/**
 * Builds segments for continuing a journey (not marking as destination)
 *
 * This function handles two cases:
 * 1. **Continuing on same line**: Only adds current station if it's not already the last segment.
 *    This handles junction stations where you might be continuing from a station already in the route.
 * 2. **Changing lines**: Adds current station (if not already last) AND next station on the new line.
 *    This creates an interchange by adding both the junction station and the first station on the new line.
 *
 * The function does NOT validate the segments (validation should happen in the caller).
 * It only performs the pure logic of building the segment array.
 *
 * @param params - Segment building parameters
 * @returns New array of segments (does not mutate currentSegments)
 *
 * @example
 * ```typescript
 * // Continuing on same line from a new station
 * const segments = buildSegmentsForContinue({
 *   currentStation: { tfl_id: 'station-a', ... },
 *   selectedLine: { tfl_id: 'northern', ... },
 *   nextStation: { tfl_id: 'station-b', ... },
 *   currentSegments: [],
 *   continueLine: { tfl_id: 'northern', ... }
 * })
 * // Result: [{ sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' }]
 *
 * // Changing lines at a junction
 * const segments = buildSegmentsForContinue({
 *   currentStation: { tfl_id: 'junction', ... },
 *   selectedLine: { tfl_id: 'northern', ... },
 *   nextStation: { tfl_id: 'next-station', ... },
 *   currentSegments: [{ sequence: 0, station_tfl_id: 'junction', line_tfl_id: 'northern' }],
 *   continueLine: { tfl_id: 'victoria', ... }
 * })
 * // Result: [
 * //   { sequence: 0, station_tfl_id: 'junction', line_tfl_id: 'northern' },
 * //   { sequence: 1, station_tfl_id: 'next-station', line_tfl_id: 'victoria' }
 * // ]
 * ```
 */
export function buildSegmentsForContinue(params: BuildContinueSegmentsParams): SegmentRequest[] {
  const { currentStation, selectedLine, nextStation, currentSegments, continueLine } = params

  // Check if current station is already the last segment (junction handling)
  const isCurrentStationLast = isStationLastInRoute(currentStation, currentSegments)

  // Check if we're changing lines (use tfl_id for comparison, not UUID)
  const isChangingLines = !isSameLine(continueLine, selectedLine)

  // Start with current segments, or add current station if not already last
  const updatedSegments = isCurrentStationLast
    ? [...currentSegments]
    : [
        ...currentSegments,
        {
          sequence: currentSegments.length,
          station_tfl_id: currentStation.tfl_id,
          line_tfl_id: selectedLine.tfl_id,
        },
      ]

  // If changing lines, add next station on new line (creates interchange)
  if (isChangingLines) {
    updatedSegments.push({
      sequence: updatedSegments.length,
      station_tfl_id: nextStation.tfl_id,
      line_tfl_id: continueLine.tfl_id,
    })
  }

  return updatedSegments
}

/**
 * Parameters for building segments when marking a station as destination
 */
export interface BuildDestinationSegmentsParams {
  /** Current station user is at (may or may not be in route already) */
  currentStation: StationResponse
  /** Line user is currently on */
  selectedLine: LineResponse
  /** Station to mark as destination (end of route) */
  destinationStation: StationResponse
  /** Current route segments */
  currentSegments: SegmentRequest[]
}

/**
 * Builds segments for marking a station as destination (end of route)
 *
 * This function adds the current station (if not already last) and then adds
 * the destination station with line_tfl_id set to null, which signals this is
 * the final destination and no further travel is expected.
 *
 * The destination marker (null line_tfl_id) is a special case used by the backend
 * to indicate the route terminus. It's different from a regular segment which
 * always has a line associated with it.
 *
 * The function does NOT validate the segments or perform the save operation.
 * It only performs the pure logic of building the segment array.
 *
 * @param params - Segment building parameters
 * @returns New array of segments (does not mutate currentSegments)
 *
 * @example
 * ```typescript
 * // Marking destination when current station is not in route
 * const segments = buildSegmentsForDestination({
 *   currentStation: { tfl_id: 'station-a', ... },
 *   selectedLine: { tfl_id: 'northern', ... },
 *   destinationStation: { tfl_id: 'destination', ... },
 *   currentSegments: []
 * })
 * // Result: [
 * //   { sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' },
 * //   { sequence: 1, station_tfl_id: 'destination', line_tfl_id: null }
 * // ]
 *
 * // Marking destination when current station is already last
 * const segments = buildSegmentsForDestination({
 *   currentStation: { tfl_id: 'station-a', ... },
 *   selectedLine: { tfl_id: 'northern', ... },
 *   destinationStation: { tfl_id: 'destination', ... },
 *   currentSegments: [{ sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' }]
 * })
 * // Result: [
 * //   { sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' },
 * //   { sequence: 1, station_tfl_id: 'destination', line_tfl_id: null }
 * // ]
 * ```
 */
export function buildSegmentsForDestination(
  params: BuildDestinationSegmentsParams
): SegmentRequest[] {
  const { currentStation, selectedLine, destinationStation, currentSegments } = params

  // Check if current station is already the last segment
  const isCurrentStationLast = isStationLastInRoute(currentStation, currentSegments)

  // Add current station if not already last
  const updatedSegments = isCurrentStationLast
    ? [...currentSegments]
    : [
        ...currentSegments,
        {
          sequence: currentSegments.length,
          station_tfl_id: currentStation.tfl_id,
          line_tfl_id: selectedLine.tfl_id,
        },
      ]

  // Add destination marker (null line_tfl_id indicates destination)
  updatedSegments.push({
    sequence: updatedSegments.length,
    station_tfl_id: destinationStation.tfl_id,
    line_tfl_id: null,
  })

  return updatedSegments
}

/**
 * Result of computing resume state from segments
 */
export interface ResumeStateResult {
  /** Station to resume from (last segment's station) */
  station: StationResponse | null
  /** Line to resume on (last segment's line, or previous if last is destination) */
  line: LineResponse | null
}

/**
 * Removes destination marker segments from a route
 *
 * Destination markers are segments with line_tfl_id === null, which indicate
 * the final destination of a route. This function filters them out and returns
 * only the segments representing actual travel legs.
 *
 * This is commonly used when editing a route, where you want to:
 * 1. Remove the destination marker
 * 2. Continue building from the last actual travel segment
 *
 * @param segments - Route segments (may include destination markers)
 * @returns New array with only non-destination segments (does not mutate input)
 *
 * @example
 * ```typescript
 * const segments = [
 *   { sequence: 0, station_tfl_id: 'southgate', line_tfl_id: 'piccadilly' },
 *   { sequence: 1, station_tfl_id: 'leicester-square', line_tfl_id: null }
 * ]
 * const result = removeDestinationMarker(segments)
 * // Result: [{ sequence: 0, station_tfl_id: 'southgate', line_tfl_id: 'piccadilly' }]
 * ```
 */
export function removeDestinationMarker(segments: SegmentRequest[]): SegmentRequest[] {
  return segments.filter((seg) => seg.line_tfl_id !== null)
}

/**
 * Computes the station and line to resume from based on last segment
 *
 * This function is used when:
 * - Editing an existing route (resume from last segment)
 * - After deleting a segment (resume from new last segment)
 * - After clearing destination marker (resume building from previous state)
 *
 * Special case: If the last segment is a destination marker (line_tfl_id === null),
 * we look at the previous segment to determine which line to resume on.
 *
 * @param segments - Current route segments
 * @param stations - All available stations (for lookup)
 * @param lines - All available lines (for lookup)
 * @returns Resume state (station and line) or null if no segments
 *
 * @example
 * ```typescript
 * // Resume from a regular segment
 * const result = computeResumeState(
 *   [{ sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' }],
 *   stations,
 *   lines
 * )
 * // Result: { station: StationA, line: Northern }
 *
 * // Resume from destination marker (uses previous segment's line)
 * const result = computeResumeState(
 *   [
 *     { sequence: 0, station_tfl_id: 'station-a', line_tfl_id: 'northern' },
 *     { sequence: 1, station_tfl_id: 'destination', line_tfl_id: null }
 *   ],
 *   stations,
 *   lines
 * )
 * // Result: { station: Destination, line: Northern }
 *
 * // Empty segments
 * const result = computeResumeState([], stations, lines)
 * // Result: null
 * ```
 */
export function computeResumeState(
  segments: SegmentRequest[],
  stations: StationResponse[],
  lines: LineResponse[]
): ResumeStateResult | null {
  if (segments.length === 0) return null

  const lastSegment = segments[segments.length - 1]

  // Find the station for the last segment
  const lastStation = stations.find((s) => s.tfl_id === lastSegment.station_tfl_id) ?? null

  // If last segment has a line, use it; otherwise look at previous segment
  let resumeLine: LineResponse | null = null
  if (lastSegment.line_tfl_id) {
    resumeLine = lines.find((l) => l.tfl_id === lastSegment.line_tfl_id) ?? null
  } else if (segments.length > 1) {
    // Last segment is destination marker (null line), use previous segment's line
    const prevSegment = segments[segments.length - 2]
    if (prevSegment.line_tfl_id) {
      resumeLine = lines.find((l) => l.tfl_id === prevSegment.line_tfl_id) ?? null
    }
  }

  return {
    station: lastStation,
    line: resumeLine,
  }
}

/**
 * Removes segments from a sequence number onwards and resequences remaining segments
 *
 * This function is used when deleting a segment, which also removes all subsequent
 * segments to maintain route consistency (truncation). After deletion, remaining segments are
 * resequenced to ensure contiguous sequence numbers (0, 1, 2, ...).
 *
 * The function also computes truncation context to support resuming route building:
 * - If deleting from sequence 0: returns null resume context (route becomes empty)
 * - If deleting from sequence N > 0: returns station/line from last remaining segment
 *
 * The truncation context enables the UI to resume building from the correct station/line
 * after deletion, rather than resetting to initial state.
 *
 * The function does NOT validate the deletion (validation should happen in the caller).
 * It only performs the pure logic of filtering, resequencing, and computing resume context.
 *
 * @param sequence - Sequence number to delete from (inclusive)
 * @param segments - Current route segments
 * @param stations - All available stations (for looking up truncation context)
 * @param lines - All available lines (for looking up truncation context)
 * @returns DeletionResult with new segments and resume context (does not mutate segments)
 *
 * @example
 * ```typescript
 * // Delete segment 2 and all subsequent segments
 * const segments = [
 *   { sequence: 0, station_tfl_id: 'a', line_tfl_id: 'northern' },
 *   { sequence: 1, station_tfl_id: 'b', line_tfl_id: 'northern' },
 *   { sequence: 2, station_tfl_id: 'c', line_tfl_id: 'victoria' },
 *   { sequence: 3, station_tfl_id: 'd', line_tfl_id: 'victoria' }
 * ]
 * const result = deleteSegmentAndResequence(2, segments, stations, lines)
 * // Result: {
 * //   segments: [
 * //     { sequence: 0, station_tfl_id: 'a', line_tfl_id: 'northern' },
 * //     { sequence: 1, station_tfl_id: 'b', line_tfl_id: 'northern' }
 * //   ],
 * //   resumeFrom: { station: StationB, line: NorthernLine }
 * // }
 *
 * // Delete from start (clears all segments)
 * const result = deleteSegmentAndResequence(0, segments, stations, lines)
 * // Result: {
 * //   segments: [],
 * //   resumeFrom: { station: null, line: null }
 * // }
 * ```
 */
export function deleteSegmentAndResequence(
  sequence: number,
  segments: SegmentRequest[],
  stations: StationResponse[],
  lines: LineResponse[]
): DeletionResult {
  // Filter and resequence remaining segments
  const remainingSegments = segments
    .filter((seg) => seg.sequence < sequence)
    .map((seg, index) => ({ ...seg, sequence: index }))

  // Compute truncation context using existing computeResumeState logic
  // This handles the case where last segment is a destination marker (null line)
  const resumeState = computeResumeState(remainingSegments, stations, lines)

  return {
    segments: remainingSegments,
    resumeFrom: {
      station: resumeState?.station ?? null,
      line: resumeState?.line ?? null,
    },
  }
}
