/**
 * TfL Brand Guidelines for Line Colors and Text
 *
 * Per TfL brand guidelines:
 * - Most lines use white text reversed out of the line color
 * - Circle, Hammersmith & City, and Waterloo & City use Corporate Blue text
 *
 * Corporate Blue: PMS 072, RGB(0, 25, 168), #0019A8
 */

import type { LineResponse } from './api'

/**
 * Lines that use Corporate Blue text instead of white
 */
const LIGHT_LINES = ['circle', 'hammersmith-city', 'waterloo-city']

/**
 * TfL Corporate Blue color
 */
export const CORPORATE_BLUE = '#0019A8'

/**
 * White color for most line text
 */
export const WHITE = '#FFFFFF'

/**
 * Get the correct text color for a TfL line following brand guidelines
 *
 * @param tflId - The TfL ID of the line (e.g., 'piccadilly', 'circle')
 * @returns Hex color code for text (white or Corporate Blue)
 */
export function getLineTextColor(tflId: string): string {
  const normalizedId = tflId.toLowerCase()
  return LIGHT_LINES.includes(normalizedId) ? CORPORATE_BLUE : WHITE
}

/**
 * Sort lines alphabetically by name
 * Currently all lines are Underground, but future-proof for multiple modes
 * Underground lines first, then other modes (Overground, etc.) alphabetically
 *
 * @param lines - Array of line objects
 * @returns Sorted array of lines
 */
export function sortLines(lines: LineResponse[]): LineResponse[] {
  return [...lines].sort((a, b) => a.name.localeCompare(b.name))
}
