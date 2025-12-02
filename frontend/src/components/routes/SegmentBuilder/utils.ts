/**
 * Utility functions for station and line lookups in SegmentBuilder
 *
 * These pure functions provide simple array lookups and comparisons
 * for working with TfL stations and lines.
 */

import type { StationResponse, LineResponse } from '@/types'

/**
 * Finds a station by its TfL ID
 *
 * @param tflId - The TfL station ID to search for
 * @param stations - Array of available stations
 * @returns The matching station, or null if not found
 *
 * @example
 * ```ts
 * const station = findStationByTflId('940GZZLUKSX', stations)
 * if (station) {
 *   console.log(station.name) // "King's Cross St. Pancras"
 * }
 * ```
 */
export function findStationByTflId(
  tflId: string,
  stations: StationResponse[]
): StationResponse | null {
  return stations.find((s) => s.tfl_id === tflId) ?? null
}

/**
 * Finds a line by its TfL ID
 *
 * @param tflId - The TfL line ID to search for
 * @param lines - Array of available lines
 * @returns The matching line, or null if not found
 *
 * @example
 * ```ts
 * const line = findLineByTflId('northern', lines)
 * if (line) {
 *   console.log(line.name) // "Northern"
 * }
 * ```
 */
export function findLineByTflId(tflId: string, lines: LineResponse[]): LineResponse | null {
  return lines.find((l) => l.tfl_id === tflId) ?? null
}

/**
 * Checks if two lines are the same based on their TfL ID
 *
 * This function safely handles null values and uses tfl_id for comparison
 * rather than database UUIDs, ensuring consistency across the application.
 *
 * @param line1 - First line to compare (can be null)
 * @param line2 - Second line to compare (can be null)
 * @returns true if both lines are non-null and have the same tfl_id, false otherwise
 *
 * @example
 * ```ts
 * const northern = { tfl_id: 'northern', name: 'Northern' }
 * const victoria = { tfl_id: 'victoria', name: 'Victoria' }
 *
 * isSameLine(northern, northern) // true
 * isSameLine(northern, victoria) // false
 * isSameLine(northern, null)     // false
 * isSameLine(null, null)         // false
 * ```
 */
export function isSameLine(line1: LineResponse | null, line2: LineResponse | null): boolean {
  if (!line1 || !line2) return false
  return line1.tfl_id === line2.tfl_id
}
