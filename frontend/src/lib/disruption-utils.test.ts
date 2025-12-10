import { describe, it, expect } from 'vitest'
import { getWorstDisruptionForRoute } from './disruption-utils'
import type { RouteDisruptionResponse, DisruptionResponse } from '@/types'

// Helper function to create mock disruption data
const createDisruption = (
  routeId: string,
  severity: number,
  overrides?: Partial<DisruptionResponse>
): RouteDisruptionResponse => ({
  route_id: routeId,
  route_name: 'Test Route',
  disruption: {
    line_id: 'victoria',
    line_name: 'Victoria',
    mode: 'tube',
    status_severity: severity,
    status_severity_description: severity === 10 ? 'Good Service' : 'Minor Delays',
    reason: 'Test reason',
    created_at: '2025-01-01T10:00:00Z',
    affected_routes: null,
    ...overrides,
  },
  affected_segments: [0, 1],
  affected_stations: ['940GZZLUOXC'],
})

describe('getWorstDisruptionForRoute', () => {
  describe('null and empty cases', () => {
    it('should return null when disruptions is null', () => {
      const result = getWorstDisruptionForRoute(null, 'route-1')
      expect(result).toBeNull()
    })

    it('should return null when disruptions array is empty', () => {
      const result = getWorstDisruptionForRoute([], 'route-1')
      expect(result).toBeNull()
    })

    it('should return null when no disruptions match the route ID', () => {
      const disruptions = [createDisruption('route-2', 6), createDisruption('route-3', 8)]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')
      expect(result).toBeNull()
    })
  })

  describe('single disruption', () => {
    it('should return the single disruption when only one matches', () => {
      const disruptions = [createDisruption('route-1', 6), createDisruption('route-2', 8)]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.route_id).toBe('route-1')
      expect(result?.disruption.status_severity).toBe(6)
    })
  })

  describe('multiple disruptions', () => {
    it('should return the worst (lowest severity) disruption when multiple match', () => {
      const disruptions = [
        createDisruption('route-1', 10), // Good Service
        createDisruption('route-1', 6), // Minor Delays
        createDisruption('route-1', 20), // Severe Delays
        createDisruption('route-2', 5), // Different route
      ]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.disruption.status_severity).toBe(6)
    })

    it('should return the most severe disruption (severity 1) over others', () => {
      const disruptions = [
        createDisruption('route-1', 8),
        createDisruption('route-1', 1), // Most severe (closure/suspension)
        createDisruption('route-1', 6),
      ]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.disruption.status_severity).toBe(1)
    })

    it('should handle multiple routes with overlapping severity codes', () => {
      const disruptions = [
        createDisruption('route-1', 10),
        createDisruption('route-2', 5),
        createDisruption('route-1', 7),
        createDisruption('route-3', 3),
      ]

      const result1 = getWorstDisruptionForRoute(disruptions, 'route-1')
      expect(result1?.disruption.status_severity).toBe(7)

      const result2 = getWorstDisruptionForRoute(disruptions, 'route-2')
      expect(result2?.disruption.status_severity).toBe(5)

      const result3 = getWorstDisruptionForRoute(disruptions, 'route-3')
      expect(result3?.disruption.status_severity).toBe(3)
    })
  })

  describe('edge cases', () => {
    it('should handle severity 10 (Good Service) correctly', () => {
      const disruptions = [createDisruption('route-1', 10)]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.disruption.status_severity).toBe(10)
    })

    it('should prefer severity 5 over severity 10', () => {
      const disruptions = [createDisruption('route-1', 10), createDisruption('route-1', 5)]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result?.disruption.status_severity).toBe(5)
    })

    it('should handle all disruptions being for the same route', () => {
      const disruptions = [
        createDisruption('route-1', 6),
        createDisruption('route-1', 8),
        createDisruption('route-1', 7),
      ]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result?.disruption.status_severity).toBe(6)
    })

    it('should return the first disruption when all have the same severity', () => {
      const disruptions = [
        createDisruption('route-1', 6),
        createDisruption('route-1', 6),
        createDisruption('route-1', 6),
      ]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.disruption.status_severity).toBe(6)
      // Should be the first one since they're all equal
      expect(result).toBe(disruptions[0])
    })
  })

  describe('data structure validation', () => {
    it('should preserve all fields of the returned disruption', () => {
      const disruptions = [
        createDisruption('route-1', 6, {
          line_id: 'piccadilly',
          line_name: 'Piccadilly',
          reason: 'Signal failure at Kings Cross',
          status_severity_description: 'Minor Delays',
        }),
      ]
      const result = getWorstDisruptionForRoute(disruptions, 'route-1')

      expect(result).not.toBeNull()
      expect(result?.route_id).toBe('route-1')
      expect(result?.route_name).toBe('Test Route')
      expect(result?.disruption.line_id).toBe('piccadilly')
      expect(result?.disruption.line_name).toBe('Piccadilly')
      expect(result?.disruption.reason).toBe('Signal failure at Kings Cross')
      expect(result?.affected_segments).toEqual([0, 1])
      expect(result?.affected_stations).toEqual(['940GZZLUOXC'])
    })
  })
})
