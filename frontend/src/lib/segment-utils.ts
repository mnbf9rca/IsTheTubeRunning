/**
 * Utility functions for segment type conversions
 */

import type { SegmentRequest, SegmentResponse } from '@/types'

/**
 * Convert SegmentResponse to SegmentRequest by extracting only request fields.
 *
 * This prevents response-only fields (id, created_at, etc.) from leaking into requests.
 * Uses explicit field mapping rather than spread/destructuring to ensure only the
 * intended request fields are included, even if the backend adds new response-only fields.
 *
 * @param response - The segment response from the backend
 * @returns A segment request object suitable for API calls
 */
export function segmentResponseToRequest(response: SegmentResponse): SegmentRequest {
  return {
    sequence: response.sequence,
    station_tfl_id: response.station_tfl_id,
    line_tfl_id: response.line_tfl_id,
  }
}
