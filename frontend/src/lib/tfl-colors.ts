/**
 * TfL Brand Guidelines for Line Colors and Text
 *
 * Per TfL brand guidelines:
 * - Most lines use white text reversed out of the line color
 * - Circle, Hammersmith & City, and Waterloo & City use Corporate Blue text
 *
 * Corporate Blue: PMS 072, RGB(0, 25, 168), #0019A8
 *
 * Official TfL Line Colors:
 * https://tfl.gov.uk/corporate/about-tfl/how-we-work/corporate-and-social-responsibility/corporate-responsibility-and-sustainability-report
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
 * Official TfL Line Colors (hex codes)
 * These are the authoritative source for line colors in the application.
 */
const LINE_COLORS: Record<string, string> = {
  bakerloo: '#B36305',
  central: '#E32017',
  circle: '#FFD300',
  district: '#00782A',
  'hammersmith-city': '#F3A9BB',
  jubilee: '#A0A5A9',
  metropolitan: '#9B0056',
  northern: '#000000',
  piccadilly: '#003688',
  victoria: '#0098D4',
  'waterloo-city': '#95CDBA',
  // Elizabeth line (future)
  elizabeth: '#7156A5',
  // Other modes
  overground: '#EE7C0E',
  dlr: '#00A4A7',
  tram: '#84B817',
}

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
 * Get the correct background color for a TfL line
 * Overrides backend colors with official TfL brand colors
 *
 * @param tflId - The TfL ID of the line (e.g., 'piccadilly', 'northern')
 * @returns Hex color code for line background
 */
export function getLineColor(tflId: string): string {
  const normalizedId = tflId.toLowerCase()
  return LINE_COLORS[normalizedId] || '#000000' // Fallback to black if not found
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
