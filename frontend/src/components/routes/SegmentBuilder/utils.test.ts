import { describe, it, expect } from 'vitest'
import { findStationByTflId, findLineByTflId, isSameLine } from './utils'
import { StationResponse, LineResponse } from '@/lib/api'

describe('SegmentBuilder utils', () => {
  describe('findStationByTflId', () => {
    const mockStations: StationResponse[] = [
      {
        id: '123e4567-e89b-12d3-a456-426614174000',
        tfl_id: '940GZZLUKSX',
        name: "King's Cross St. Pancras",
        latitude: 51.5304,
        longitude: -0.1238,
        lines: ['northern', 'piccadilly'],
        last_updated: '2025-01-01T00:00:00Z',
        hub_naptan_code: null,
        hub_common_name: null,
      },
      {
        id: '123e4567-e89b-12d3-a456-426614174001',
        tfl_id: '940GZZLUEUS',
        name: 'Euston',
        latitude: 51.5282,
        longitude: -0.1337,
        lines: ['northern', 'victoria'],
        last_updated: '2025-01-01T00:00:00Z',
        hub_naptan_code: null,
        hub_common_name: null,
      },
    ]

    it('should find station by tfl_id', () => {
      const result = findStationByTflId('940GZZLUKSX', mockStations)
      expect(result).not.toBeNull()
      expect(result?.name).toBe("King's Cross St. Pancras")
      expect(result?.tfl_id).toBe('940GZZLUKSX')
    })

    it('should return null if station not found', () => {
      const result = findStationByTflId('nonexistent', mockStations)
      expect(result).toBeNull()
    })

    it('should return null for empty array', () => {
      const result = findStationByTflId('940GZZLUKSX', [])
      expect(result).toBeNull()
    })

    it('should handle multiple stations with same prefix', () => {
      const result = findStationByTflId('940GZZLUEUS', mockStations)
      expect(result).not.toBeNull()
      expect(result?.name).toBe('Euston')
    })
  })

  describe('findLineByTflId', () => {
    const mockLines: LineResponse[] = [
      {
        id: '223e4567-e89b-12d3-a456-426614174000',
        tfl_id: 'northern',
        name: 'Northern',
        mode: 'tube',
        last_updated: '2025-01-01T00:00:00Z',
      },
      {
        id: '223e4567-e89b-12d3-a456-426614174001',
        tfl_id: 'victoria',
        name: 'Victoria',
        mode: 'tube',
        last_updated: '2025-01-01T00:00:00Z',
      },
    ]

    it('should find line by tfl_id', () => {
      const result = findLineByTflId('northern', mockLines)
      expect(result).not.toBeNull()
      expect(result?.name).toBe('Northern')
      expect(result?.tfl_id).toBe('northern')
    })

    it('should return null if line not found', () => {
      const result = findLineByTflId('nonexistent', mockLines)
      expect(result).toBeNull()
    })

    it('should return null for empty array', () => {
      const result = findLineByTflId('northern', [])
      expect(result).toBeNull()
    })

    it('should distinguish between similar line names', () => {
      const result = findLineByTflId('victoria', mockLines)
      expect(result).not.toBeNull()
      expect(result?.name).toBe('Victoria')
    })
  })

  describe('isSameLine', () => {
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

    // Same tfl_id but different UUID (tests that we use tfl_id not UUID)
    const mockLineNorthernDifferentId: LineResponse = {
      id: 'different-uuid-here',
      tfl_id: 'northern',
      name: 'Northern',
      mode: 'tube',
      last_updated: '2025-01-01T00:00:00Z',
    }

    it('should return true for same line (same object)', () => {
      expect(isSameLine(mockLineNorthern, mockLineNorthern)).toBe(true)
    })

    it('should return true for same tfl_id (different UUIDs)', () => {
      expect(isSameLine(mockLineNorthern, mockLineNorthernDifferentId)).toBe(true)
    })

    it('should return false for different lines', () => {
      expect(isSameLine(mockLineNorthern, mockLineVictoria)).toBe(false)
    })

    it('should return false when first line is null', () => {
      expect(isSameLine(null, mockLineNorthern)).toBe(false)
    })

    it('should return false when second line is null', () => {
      expect(isSameLine(mockLineNorthern, null)).toBe(false)
    })

    it('should return false when both lines are null', () => {
      expect(isSameLine(null, null)).toBe(false)
    })
  })
})
