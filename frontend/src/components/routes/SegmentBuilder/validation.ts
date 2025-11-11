/**
 * Pure validation functions for SegmentBuilder
 *
 * This module provides pure validation functions that can be tested in isolation
 * without React hooks or component state. All functions are pure (no side effects,
 * same input → same output) and return ValidationResult for consistent error handling.
 *
 * These functions were extracted from SegmentBuilder.tsx to eliminate code duplication
 * (4 duplicate station checks, 4 max segments checks) and enable 100% test coverage.
 *
 * @see ADR 11: Frontend State Management Pattern - Pure Function Architecture
 * @see Issue #95: Extract Validation & Types Module from SegmentBuilder
 */

import type { StationResponse, LineResponse } from '../../../lib/api'
import type { SegmentRequest, ValidationResult } from './types'

/**
 * Maximum number of segments allowed per route
 *
 * This limit prevents routes from becoming too complex and ensures reasonable
 * performance when validating routes against the TfL network graph.
 *
 * Business Rule: A typical London commute has 5-10 segments. 20 segments allows
 * for complex routes with multiple interchanges while preventing abuse.
 */
export const MAX_ROUTE_SEGMENTS = 20

/**
 * Checks if a station is the last segment in the route
 *
 * This helper is used by validateNotDuplicate to implement the "allow last" logic,
 * which permits continuing a journey from a junction station that's already in the route.
 *
 * @param station - Station to check
 * @param segments - Current route segments
 * @returns true if station is the last segment, false otherwise
 *
 * @example
 * ```typescript
 * const segments = [
 *   { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: 'northern' },
 *   { sequence: 1, station_tfl_id: 'euston', line_tfl_id: null }
 * ]
 * const euston = { tfl_id: 'euston', name: 'Euston', ... }
 * isStationLastInRoute(euston, segments) // → true
 * ```
 */
export function isStationLastInRoute(
  station: StationResponse,
  segments: SegmentRequest[]
): boolean {
  if (segments.length === 0) return false
  const lastSegment = segments[segments.length - 1]
  return lastSegment.station_tfl_id === station.tfl_id
}

/**
 * Validates that a station is not a duplicate in the route
 *
 * Routes must be acyclic (cannot visit the same station twice) to ensure clear
 * journey paths. This function checks if a station is already in the route.
 *
 * Special case: When `allowLast` is true, the station is allowed if it's the
 * last segment in the route. This enables continuing a journey from a junction
 * station where you might change lines.
 *
 * @param station - Station to check for duplication
 * @param segments - Current route segments
 * @param options.allowLast - Allow station if it's the last segment (default: false)
 * @returns ValidationResult indicating success or error
 *
 * @example
 * ```typescript
 * // Simple duplicate check
 * const result = validateNotDuplicate(station, segments)
 * if (!result.valid) {
 *   setError(result.error)
 *   return
 * }
 *
 * // Allow last segment (junction station)
 * const result = validateNotDuplicate(station, segments, { allowLast: true })
 * ```
 */
export function validateNotDuplicate(
  station: StationResponse,
  segments: SegmentRequest[],
  options: { allowLast?: boolean } = {}
): ValidationResult {
  const { allowLast = false } = options

  // If allowLast is true and this station is the last in the route, it's valid
  if (allowLast && isStationLastInRoute(station, segments)) {
    return { valid: true }
  }

  // Check if station already exists in route
  const isDuplicate = segments.some((seg) => seg.station_tfl_id === station.tfl_id)

  if (isDuplicate) {
    return {
      valid: false,
      error: `This station (${station.name}) is already in your route. Routes cannot visit the same station twice.`,
    }
  }

  return { valid: true }
}

/**
 * Validates that adding segments won't exceed maximum limit
 *
 * Prevents routes from becoming too complex by enforcing a maximum segment count.
 * This check should be performed before adding new segments to the route.
 *
 * @param currentCount - Current number of segments in the route
 * @param additionalCount - Number of segments to add (default: 1)
 * @param maxSegments - Maximum allowed segments (default: MAX_ROUTE_SEGMENTS)
 * @returns ValidationResult indicating success or error
 *
 * @example
 * ```typescript
 * // Check if we can add 1 segment
 * const result = validateMaxSegments(segments.length)
 * if (!result.valid) {
 *   setError(result.error)
 *   return
 * }
 *
 * // Check if we can add 2 segments (line change creates 2 segments)
 * const result = validateMaxSegments(segments.length, 2)
 * ```
 */
export function validateMaxSegments(
  currentCount: number,
  additionalCount: number = 1,
  maxSegments: number = MAX_ROUTE_SEGMENTS
): ValidationResult {
  if (currentCount + additionalCount > maxSegments) {
    return {
      valid: false,
      error: `Maximum ${maxSegments} segments allowed per route.`,
    }
  }

  return { valid: true }
}

/**
 * Validates that a segment can be deleted
 *
 * Prevents deletion of destination segments (last segment with null line_tfl_id)
 * and validates sequence numbers are within bounds.
 *
 * Business Rule: The destination station cannot be deleted directly. To shorten
 * a route, users must delete an earlier station, which automatically removes all
 * subsequent segments.
 *
 * @param sequence - Sequence number of segment to delete
 * @param segments - Current route segments
 * @returns ValidationResult indicating success or error
 *
 * @example
 * ```typescript
 * const result = validateCanDeleteSegment(2, segments)
 * if (!result.valid) {
 *   setError(result.error)
 *   return
 * }
 * // Safe to delete segment at index 2
 * ```
 */
export function validateCanDeleteSegment(
  sequence: number,
  segments: SegmentRequest[]
): ValidationResult {
  // Validate sequence is within bounds
  if (sequence < 0 || sequence >= segments.length) {
    return {
      valid: false,
      error: 'Invalid segment sequence number.',
    }
  }

  // Prevent deletion of destination station (last segment with line_tfl_id === null)
  const isDestination = sequence === segments.length - 1 && segments[sequence].line_tfl_id === null

  if (isDestination) {
    return {
      valid: false,
      error:
        'Cannot delete the destination station. Delete an earlier station to shorten your route.',
    }
  }

  return { valid: true }
}

/**
 * Calculate how many additional segments will be added based on junction scenario
 *
 * When continuing a journey or marking a destination, we may need to add:
 * - 0 segments: Already at junction, continuing on same line
 * - 1 segment: Either adding first station OR already at junction but changing lines
 * - 2 segments: Adding station + line change (current station + interchange)
 *
 * @param currentStation - The current station being added
 * @param currentLine - The line we're currently traveling on
 * @param nextLine - The line we want to continue on
 * @param segments - Current route segments
 * @returns Number of segments that will be added (0, 1, or 2)
 *
 * @example
 * // At Leicester Square, continuing on same Piccadilly line: 0 segments
 * calculateAdditionalSegments(leicesterSq, piccadilly, piccadilly, [...]) // => 0
 *
 * // At Leicester Square, changing to Northern line: 1 segment (interchange)
 * calculateAdditionalSegments(leicesterSq, piccadilly, northern, [...]) // => 1
 *
 * // Adding new station on same line: 1 segment
 * calculateAdditionalSegments(newStation, piccadilly, piccadilly, [...]) // => 1
 *
 * // Adding new station with line change: 2 segments
 * calculateAdditionalSegments(newStation, piccadilly, northern, [...]) // => 2
 */
export function calculateAdditionalSegments(
  currentStation: StationResponse,
  currentLine: LineResponse,
  nextLine: LineResponse,
  segments: SegmentRequest[]
): number {
  const isChangingLines = currentLine.tfl_id !== nextLine.tfl_id
  const isCurrentStationLast = isStationLastInRoute(currentStation, segments)

  if (isCurrentStationLast) {
    // Current station already in route - won't be added again
    return isChangingLines ? 1 : 0
  } else {
    // Current station will be added
    return isChangingLines ? 2 : 1
  }
}
