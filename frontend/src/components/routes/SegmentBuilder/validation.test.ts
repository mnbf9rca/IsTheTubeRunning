/**
 * Tests for validation functions
 *
 * Target: 100% statement and branch coverage for all validation functions
 *
 * @see validation.ts
 */

import { describe, it, expect } from 'vitest'
import {
  validateNotDuplicate,
  validateMaxSegments,
  validateCanDeleteSegment,
  isStationLastInRoute,
  MAX_ROUTE_SEGMENTS,
} from './validation'
import type { StationResponse } from '../../../lib/api'
import type { SegmentRequest } from './types'

describe('isStationLastInRoute', () => {
  const mockStation: StationResponse = {
    id: 'uuid-123',
    tfl_id: 'kings-cross',
    name: 'Kings Cross',
    latitude: 51.5,
    longitude: -0.1,
    lines: ['northern', 'piccadilly'],
    last_updated: '2024-01-01',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  it('should return false for empty segments array', () => {
    expect(isStationLastInRoute(mockStation, [])).toBe(false)
  })

  it('should return true when station is last segment', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'kings-cross', line_tfl_id: null },
    ]

    expect(isStationLastInRoute(mockStation, segments)).toBe(true)
  })

  it('should return false when station is not last segment', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'euston', line_tfl_id: null },
    ]

    expect(isStationLastInRoute(mockStation, segments)).toBe(false)
  })

  it('should return true for single segment matching station', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: null },
    ]

    expect(isStationLastInRoute(mockStation, segments)).toBe(true)
  })
})

describe('validateNotDuplicate', () => {
  const mockStation: StationResponse = {
    id: 'uuid-123',
    tfl_id: 'kings-cross',
    name: 'Kings Cross',
    latitude: 51.5,
    longitude: -0.1,
    lines: ['northern', 'piccadilly'],
    last_updated: '2024-01-01',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  it('should return valid when segments array is empty', () => {
    const result = validateNotDuplicate(mockStation, [])

    expect(result.valid).toBe(true)
  })

  it('should return valid when station is not in segments', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'camden', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments)

    expect(result.valid).toBe(true)
  })

  it('should return invalid when station is duplicate', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'euston', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Kings Cross')
      expect(result.error).toContain('already in your route')
      expect(result.error).toContain('cannot visit the same station twice')
    }
  })

  it('should return valid when station is last and allowLast=true', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'kings-cross', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments, { allowLast: true })

    expect(result.valid).toBe(true)
  })

  it('should return invalid when station is duplicate but not last with allowLast=true', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'euston', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments, { allowLast: true })

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Kings Cross')
      expect(result.error).toContain('already in your route')
    }
  })

  it('should return valid for single segment matching station with allowLast=true', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'kings-cross', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments, { allowLast: true })

    expect(result.valid).toBe(true)
  })

  it('should return invalid when station is duplicate in middle of route with allowLast=true', () => {
    const segments: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'kings-cross', line_tfl_id: 'piccadilly' },
      { sequence: 2, station_tfl_id: 'finsbury-park', line_tfl_id: null },
    ]

    const result = validateNotDuplicate(mockStation, segments, { allowLast: true })

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Kings Cross')
    }
  })
})

describe('validateMaxSegments', () => {
  it('should return valid when under limit', () => {
    const result = validateMaxSegments(5, 1, 20)

    expect(result.valid).toBe(true)
  })

  it('should return invalid when at limit', () => {
    const result = validateMaxSegments(20, 1, 20)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Maximum 20 segments')
      expect(result.error).toContain('allowed per route')
    }
  })

  it('should return invalid when would exceed limit', () => {
    const result = validateMaxSegments(18, 3, 20)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Maximum 20 segments')
    }
  })

  it('should return valid when exactly at boundary', () => {
    const result = validateMaxSegments(19, 1, 20)

    expect(result.valid).toBe(true)
  })

  it('should use default MAX_ROUTE_SEGMENTS constant', () => {
    const result = validateMaxSegments(MAX_ROUTE_SEGMENTS, 1)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain(`Maximum ${MAX_ROUTE_SEGMENTS} segments`)
    }
  })

  it('should handle adding multiple segments', () => {
    const result = validateMaxSegments(15, 5, 20)

    expect(result.valid).toBe(true)
  })

  it('should return invalid when adding multiple segments would exceed', () => {
    const result = validateMaxSegments(15, 6, 20)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Maximum 20 segments')
    }
  })

  it('should use default additionalCount of 1 when not specified', () => {
    const result = validateMaxSegments(19)

    expect(result.valid).toBe(true)
  })
})

describe('validateCanDeleteSegment', () => {
  const mockSegments: SegmentRequest[] = [
    { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
    { sequence: 1, station_tfl_id: 'kings-cross', line_tfl_id: 'piccadilly' },
    { sequence: 2, station_tfl_id: 'finsbury-park', line_tfl_id: null },
  ]

  it('should return valid for middle segment', () => {
    const result = validateCanDeleteSegment(1, mockSegments)

    expect(result.valid).toBe(true)
  })

  it('should return valid for first segment', () => {
    const result = validateCanDeleteSegment(0, mockSegments)

    expect(result.valid).toBe(true)
  })

  it('should return invalid for destination segment (last with null line)', () => {
    const result = validateCanDeleteSegment(2, mockSegments)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Cannot delete the destination station')
      expect(result.error).toContain('Delete an earlier station')
    }
  })

  it('should return invalid for negative sequence', () => {
    const result = validateCanDeleteSegment(-1, mockSegments)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Invalid segment sequence number')
    }
  })

  it('should return invalid for sequence out of bounds', () => {
    const result = validateCanDeleteSegment(10, mockSegments)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Invalid segment sequence number')
    }
  })

  it('should return invalid for sequence equal to segments length', () => {
    const result = validateCanDeleteSegment(mockSegments.length, mockSegments)

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Invalid segment sequence number')
    }
  })

  it('should return valid for last segment if it has a line (not destination)', () => {
    const segmentsWithLineAtEnd: SegmentRequest[] = [
      { sequence: 0, station_tfl_id: 'euston', line_tfl_id: 'northern' },
      { sequence: 1, station_tfl_id: 'kings-cross', line_tfl_id: 'piccadilly' },
    ]

    const result = validateCanDeleteSegment(1, segmentsWithLineAtEnd)

    expect(result.valid).toBe(true)
  })

  it('should return invalid for empty segments array', () => {
    const result = validateCanDeleteSegment(0, [])

    expect(result.valid).toBe(false)
    if (!result.valid) {
      expect(result.error).toContain('Invalid segment sequence number')
    }
  })
})
