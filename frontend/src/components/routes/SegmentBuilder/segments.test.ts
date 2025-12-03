import { describe, it, expect } from 'vitest'
import {
  buildSegmentsForContinue,
  buildSegmentsForDestination,
  computeResumeState,
  deleteSegmentAndResequence,
  removeDestinationMarker,
} from './segments'
import type { StationResponse, LineResponse } from '@/types'
import { SegmentRequest } from './types'

describe('SegmentBuilder segments', () => {
  // Mock stations
  const mockStationA: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174000',
    tfl_id: 'station-a',
    name: 'Station A',
    latitude: 51.5,
    longitude: -0.1,
    lines: ['northern'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  const mockStationB: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174001',
    tfl_id: 'station-b',
    name: 'Station B',
    latitude: 51.51,
    longitude: -0.11,
    lines: ['northern'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  const mockStationC: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174002',
    tfl_id: 'station-c',
    name: 'Station C',
    latitude: 51.52,
    longitude: -0.12,
    lines: ['northern', 'victoria'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  const mockStationD: StationResponse = {
    id: '123e4567-e89b-12d3-a456-426614174003',
    tfl_id: 'station-d',
    name: 'Station D',
    latitude: 51.53,
    longitude: -0.13,
    lines: ['victoria'],
    last_updated: '2025-01-01T00:00:00Z',
    hub_naptan_code: null,
    hub_common_name: null,
  }

  // Mock lines
  const mockLineNorthern: LineResponse = {
    id: '223e4567-e89b-12d3-a456-426614174000',
    tfl_id: 'northern',
    name: 'Northern',
    mode: 'tube',
    last_updated: '2025-01-01T00:00:00Z',
  }

  const mockLineVictoria: LineResponse = {
    id: '223e4567-e89b-12d3-a456-426614174001',
    tfl_id: 'victoria',
    name: 'Victoria',
    mode: 'tube',
    last_updated: '2025-01-01T00:00:00Z',
  }

  const mockStations = [mockStationA, mockStationB, mockStationC, mockStationD]
  const mockLines = [mockLineNorthern, mockLineVictoria]

  describe('buildSegmentsForContinue', () => {
    it('should add current station when starting from empty segments', () => {
      const result = buildSegmentsForContinue({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        currentSegments: [],
        continueLine: mockLineNorthern,
      })

      expect(result).toHaveLength(1)
      expect(result[0]).toEqual({
        sequence: 0,
        station_tfl_id: 'station-a',
        line_tfl_id: 'northern',
      })
    })

    it('should not duplicate current station if already last in route', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        currentSegments: existingSegments,
        continueLine: mockLineNorthern,
      })

      expect(result).toHaveLength(1)
      expect(result[0].station_tfl_id).toBe('station-a')
    })

    it('should add next station when changing lines', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-c',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationC,
        selectedLine: mockLineNorthern,
        nextStation: mockStationD,
        currentSegments: existingSegments,
        continueLine: mockLineVictoria, // Changing lines!
      })

      expect(result).toHaveLength(3)
      expect(result[2]).toEqual({
        sequence: 2,
        station_tfl_id: 'station-d',
        line_tfl_id: 'victoria',
      })
    })

    it('should not add next station when continuing on same line', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        currentSegments: existingSegments,
        continueLine: mockLineNorthern, // Same line
      })

      expect(result).toHaveLength(1)
      expect(result[0].station_tfl_id).toBe('station-a')
    })

    it('should add current station when not last, even on same line', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationB, // Different from last
        selectedLine: mockLineNorthern,
        nextStation: mockStationC,
        currentSegments: existingSegments,
        continueLine: mockLineNorthern,
      })

      expect(result).toHaveLength(2)
      expect(result[1]).toEqual({
        sequence: 1,
        station_tfl_id: 'station-b',
        line_tfl_id: 'northern',
      })
    })

    it('should handle line change from junction station (complex scenario)', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-c',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationC, // Junction station, already last
        selectedLine: mockLineNorthern,
        nextStation: mockStationD,
        currentSegments: existingSegments,
        continueLine: mockLineVictoria, // Changing to Victoria
      })

      // Should not duplicate station-c, but should add station-d
      expect(result).toHaveLength(3)
      expect(result[0].station_tfl_id).toBe('station-a')
      expect(result[1].station_tfl_id).toBe('station-c')
      expect(result[2]).toEqual({
        sequence: 2,
        station_tfl_id: 'station-d',
        line_tfl_id: 'victoria',
      })
    })

    it('should handle changing lines when current station not in route', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationC, // Not in route yet
        selectedLine: mockLineNorthern,
        nextStation: mockStationD,
        currentSegments: existingSegments,
        continueLine: mockLineVictoria, // Changing lines
      })

      // Should add station-c on northern, then station-d on victoria
      expect(result).toHaveLength(3)
      expect(result[1]).toEqual({
        sequence: 1,
        station_tfl_id: 'station-c',
        line_tfl_id: 'northern',
      })
      expect(result[2]).toEqual({
        sequence: 2,
        station_tfl_id: 'station-d',
        line_tfl_id: 'victoria',
      })
    })

    it('should use tfl_id for line comparison (not UUID)', () => {
      // Create a line with same tfl_id but different UUID
      const mockLineNorthernDifferentUuid: LineResponse = {
        id: 'different-uuid-12345',
        tfl_id: 'northern', // Same tfl_id
        name: 'Northern',
        mode: 'tube',
        last_updated: '2025-01-01T00:00:00Z',
      }

      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForContinue({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        nextStation: mockStationB,
        currentSegments: existingSegments,
        continueLine: mockLineNorthernDifferentUuid, // Different UUID, same tfl_id
      })

      // Should NOT add next station (same line by tfl_id)
      expect(result).toHaveLength(1)
    })
  })

  describe('buildSegmentsForDestination', () => {
    it('should add current and destination when starting from empty', () => {
      const result = buildSegmentsForDestination({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        destinationStation: mockStationB,
        currentSegments: [],
      })

      expect(result).toHaveLength(2)
      expect(result[0]).toEqual({
        sequence: 0,
        station_tfl_id: 'station-a',
        line_tfl_id: 'northern',
      })
      expect(result[1]).toEqual({
        sequence: 1,
        station_tfl_id: 'station-b',
        line_tfl_id: null, // Destination marker
      })
    })

    it('should not duplicate current station if already last', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForDestination({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        destinationStation: mockStationB,
        currentSegments: existingSegments,
      })

      expect(result).toHaveLength(2)
      expect(result[0].station_tfl_id).toBe('station-a')
      expect(result[1]).toEqual({
        sequence: 1,
        station_tfl_id: 'station-b',
        line_tfl_id: null,
      })
    })

    it('should add both current and destination when current not last', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForDestination({
        currentStation: mockStationB, // Not last
        selectedLine: mockLineNorthern,
        destinationStation: mockStationC,
        currentSegments: existingSegments,
      })

      expect(result).toHaveLength(3)
      expect(result[1]).toEqual({
        sequence: 1,
        station_tfl_id: 'station-b',
        line_tfl_id: 'northern',
      })
      expect(result[2]).toEqual({
        sequence: 2,
        station_tfl_id: 'station-c',
        line_tfl_id: null,
      })
    })

    it('should correctly sequence segments', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForDestination({
        currentStation: mockStationC,
        selectedLine: mockLineNorthern,
        destinationStation: mockStationD,
        currentSegments: existingSegments,
      })

      expect(result).toHaveLength(4)
      expect(result.map((s) => s.sequence)).toEqual([0, 1, 2, 3])
    })

    it('should always set destination line_tfl_id to null', () => {
      const result = buildSegmentsForDestination({
        currentStation: mockStationA,
        selectedLine: mockLineNorthern,
        destinationStation: mockStationB,
        currentSegments: [],
      })

      const lastSegment = result[result.length - 1]
      expect(lastSegment.line_tfl_id).toBeNull()
    })

    it('should handle complex multi-segment route', () => {
      const existingSegments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: 'northern',
        },
      ]

      const result = buildSegmentsForDestination({
        currentStation: mockStationC, // Already last
        selectedLine: mockLineNorthern,
        destinationStation: mockStationD,
        currentSegments: existingSegments,
      })

      expect(result).toHaveLength(4)
      expect(result[3]).toEqual({
        sequence: 3,
        station_tfl_id: 'station-d',
        line_tfl_id: null,
      })
    })
  })

  describe('computeResumeState', () => {
    it('should return null for empty segments', () => {
      const result = computeResumeState([], mockStations, mockLines)
      expect(result).toBeNull()
    })

    it('should find station and line from single segment', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-a')
      expect(result?.line?.tfl_id).toBe('northern')
    })

    it('should find station and line from multiple segments', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: 'victoria',
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-c')
      expect(result?.line?.tfl_id).toBe('victoria')
    })

    it('should use previous segment line when last segment is destination (null line_id)', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination marker
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-b')
      expect(result?.line?.tfl_id).toBe('northern') // From previous segment
    })

    it('should return null line when station not found', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'nonexistent-station',
          line_tfl_id: 'northern',
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station).toBeNull()
      expect(result?.line?.tfl_id).toBe('northern')
    })

    it('should return null line when line not found', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'nonexistent-line',
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-a')
      expect(result?.line).toBeNull()
    })

    it('should return null line when single segment is destination', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: null, // Single destination marker (edge case)
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-a')
      expect(result?.line).toBeNull()
    })

    it('should return null line when previous segment also has null line_id', () => {
      // Edge case: Both last and previous segments have null line_id
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: null,
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null,
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-b')
      expect(result?.line).toBeNull() // Previous also null
    })

    it('should return null line when previous segment line not found in lines array', () => {
      // Edge case: Last is destination, previous has line that doesn't exist
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'nonexistent-line',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-b')
      expect(result?.line).toBeNull() // Line not found
    })

    it('should handle complex route with line change and destination', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-c',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-d',
          line_tfl_id: 'victoria',
        },
        {
          sequence: 3,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination
        },
      ]

      const result = computeResumeState(segments, mockStations, mockLines)

      expect(result).not.toBeNull()
      expect(result?.station?.tfl_id).toBe('station-b')
      expect(result?.line?.tfl_id).toBe('victoria') // From previous segment
    })
  })

  describe('deleteSegmentAndResequence', () => {
    it('should delete segment and all subsequent segments', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: 'victoria',
        },
        {
          sequence: 3,
          station_tfl_id: 'station-d',
          line_tfl_id: 'victoria',
        },
      ]

      const result = deleteSegmentAndResequence(2, segments, mockStations, mockLines)

      expect(result.segments).toHaveLength(2)
      expect(result.segments[0].station_tfl_id).toBe('station-a')
      expect(result.segments[1].station_tfl_id).toBe('station-b')
    })

    it('should resequence remaining segments correctly', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: 'victoria',
        },
      ]

      const result = deleteSegmentAndResequence(1, segments, mockStations, mockLines)

      expect(result.segments).toHaveLength(1)
      expect(result.segments[0]).toEqual({
        sequence: 0,
        station_tfl_id: 'station-a',
        line_tfl_id: 'northern',
      })
    })

    it('should return empty segments array when deleting from start', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
      ]

      const result = deleteSegmentAndResequence(0, segments, mockStations, mockLines)

      expect(result.segments).toHaveLength(0)
    })

    it('should handle deleting last segment', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination
        },
      ]

      const result = deleteSegmentAndResequence(1, segments, mockStations, mockLines)

      expect(result.segments).toHaveLength(1)
      expect(result.segments[0]).toEqual({
        sequence: 0,
        station_tfl_id: 'station-a',
        line_tfl_id: 'northern',
      })
    })

    it('should ensure sequence numbers are contiguous 0,1,2...', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: 'northern',
        },
        {
          sequence: 3,
          station_tfl_id: 'station-d',
          line_tfl_id: 'northern',
        },
      ]

      const result = deleteSegmentAndResequence(2, segments, mockStations, mockLines)

      expect(result.segments.map((s) => s.sequence)).toEqual([0, 1])
    })

    it('should not mutate original segments array', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
      ]

      const originalLength = segments.length
      deleteSegmentAndResequence(1, segments, mockStations, mockLines)

      expect(segments).toHaveLength(originalLength)
    })

    // Truncation context tests
    describe('truncation context', () => {
      it('should return null resume context when deleting from start (empty route)', () => {
        const segments: SegmentRequest[] = [
          {
            sequence: 0,
            station_tfl_id: 'station-a',
            line_tfl_id: 'northern',
          },
          {
            sequence: 1,
            station_tfl_id: 'station-b',
            line_tfl_id: 'northern',
          },
        ]

        const result = deleteSegmentAndResequence(0, segments, mockStations, mockLines)

        expect(result.segments).toHaveLength(0)
        expect(result.resumeFrom.station).toBeNull()
        expect(result.resumeFrom.line).toBeNull()
      })

      it('should return resume context from last remaining segment when deleting from middle', () => {
        const segments: SegmentRequest[] = [
          {
            sequence: 0,
            station_tfl_id: 'station-a',
            line_tfl_id: 'northern',
          },
          {
            sequence: 1,
            station_tfl_id: 'station-b',
            line_tfl_id: 'northern',
          },
          {
            sequence: 2,
            station_tfl_id: 'station-c',
            line_tfl_id: 'victoria',
          },
          {
            sequence: 3,
            station_tfl_id: 'station-d',
            line_tfl_id: 'victoria',
          },
        ]

        // Delete from sequence 2 (keeps A→B)
        const result = deleteSegmentAndResequence(2, segments, mockStations, mockLines)

        expect(result.segments).toHaveLength(2)
        expect(result.resumeFrom.station?.tfl_id).toBe('station-b')
        expect(result.resumeFrom.line?.tfl_id).toBe('northern')
      })

      it('should return resume context when deleting last segment with destination marker', () => {
        const segments: SegmentRequest[] = [
          {
            sequence: 0,
            station_tfl_id: 'station-a',
            line_tfl_id: 'northern',
          },
          {
            sequence: 1,
            station_tfl_id: 'station-b',
            line_tfl_id: 'northern',
          },
          {
            sequence: 2,
            station_tfl_id: 'station-c',
            line_tfl_id: null, // Destination marker
          },
        ]

        // Delete from sequence 2 (removes destination)
        const result = deleteSegmentAndResequence(2, segments, mockStations, mockLines)

        expect(result.segments).toHaveLength(2)
        expect(result.resumeFrom.station?.tfl_id).toBe('station-b')
        expect(result.resumeFrom.line?.tfl_id).toBe('northern')
      })

      it('should return resume context with correct line after line change', () => {
        const segments: SegmentRequest[] = [
          {
            sequence: 0,
            station_tfl_id: 'station-a',
            line_tfl_id: 'northern',
          },
          {
            sequence: 1,
            station_tfl_id: 'station-c',
            line_tfl_id: 'northern',
          },
          {
            sequence: 2,
            station_tfl_id: 'station-d',
            line_tfl_id: 'victoria', // Line change
          },
        ]

        // Delete from sequence 2 (keeps A→C on Northern)
        const result = deleteSegmentAndResequence(2, segments, mockStations, mockLines)

        expect(result.segments).toHaveLength(2)
        expect(result.resumeFrom.station?.tfl_id).toBe('station-c')
        expect(result.resumeFrom.line?.tfl_id).toBe('northern') // Should be Northern, not Victoria
      })

      it('should handle complex truncation: delete middle of multi-line route', () => {
        const segments: SegmentRequest[] = [
          {
            sequence: 0,
            station_tfl_id: 'station-a',
            line_tfl_id: 'northern',
          },
          {
            sequence: 1,
            station_tfl_id: 'station-b',
            line_tfl_id: 'northern',
          },
          {
            sequence: 2,
            station_tfl_id: 'station-c',
            line_tfl_id: 'northern',
          },
          {
            sequence: 3,
            station_tfl_id: 'station-d',
            line_tfl_id: 'victoria',
          },
        ]

        // Delete from sequence 1 (truncate to just station-a)
        const result = deleteSegmentAndResequence(1, segments, mockStations, mockLines)

        expect(result.segments).toHaveLength(1)
        expect(result.segments[0].station_tfl_id).toBe('station-a')
        expect(result.resumeFrom.station?.tfl_id).toBe('station-a')
        expect(result.resumeFrom.line?.tfl_id).toBe('northern')
      })
    })
  })

  describe('removeDestinationMarker', () => {
    it('should remove destination marker segments (line_tfl_id === null)', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination marker
        },
      ]

      const result = removeDestinationMarker(segments)

      expect(result).toHaveLength(1)
      expect(result[0].station_tfl_id).toBe('station-a')
      expect(result[0].line_tfl_id).toBe('northern')
    })

    it('should keep all segments when there is no destination marker', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: 'northern',
        },
      ]

      const result = removeDestinationMarker(segments)

      expect(result).toHaveLength(2)
      expect(result[0].station_tfl_id).toBe('station-a')
      expect(result[1].station_tfl_id).toBe('station-b')
    })

    it('should return empty array for empty input', () => {
      const segments: SegmentRequest[] = []

      const result = removeDestinationMarker(segments)

      expect(result).toHaveLength(0)
    })

    it('should not mutate the original array', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null, // Destination marker
        },
      ]

      const originalLength = segments.length
      removeDestinationMarker(segments)

      // Original array should remain unchanged
      expect(segments).toHaveLength(originalLength)
      expect(segments[1].line_tfl_id).toBeNull()
    })

    it('should handle multiple destination markers (edge case)', () => {
      const segments: SegmentRequest[] = [
        {
          sequence: 0,
          station_tfl_id: 'station-a',
          line_tfl_id: 'northern',
        },
        {
          sequence: 1,
          station_tfl_id: 'station-b',
          line_tfl_id: null,
        },
        {
          sequence: 2,
          station_tfl_id: 'station-c',
          line_tfl_id: null,
        },
      ]

      const result = removeDestinationMarker(segments)

      // Should remove all destination markers
      expect(result).toHaveLength(1)
      expect(result[0].station_tfl_id).toBe('station-a')
    })
  })
})
