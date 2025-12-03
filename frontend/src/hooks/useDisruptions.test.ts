import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useDisruptions } from './useDisruptions'
import { ApiError } from '../lib/api'
import type { DisruptionResponse } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getDisruptions: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useDisruptions', () => {
  const mockDisruptionsResponse: DisruptionResponse[] = [
    {
      line_id: 'piccadilly',
      line_name: 'Piccadilly',
      mode: 'tube',
      status_severity: 6,
      status_severity_description: 'Minor Delays',
      reason: 'Signal failure',
      created_at: '2025-01-01T10:00:00Z',
      affected_routes: [
        {
          name: 'Piccadilly Line',
          direction: 'inbound',
          affected_stations: ['Heathrow Airport', 'Cockfosters'],
        },
      ],
    },
    {
      line_id: 'northern',
      line_name: 'Northern',
      mode: 'tube',
      status_severity: 10,
      status_severity_description: 'Good Service',
      reason: null,
      created_at: null,
      affected_routes: null,
    },
    {
      line_id: 'victoria',
      line_name: 'Victoria',
      mode: 'tube',
      status_severity: 20,
      status_severity_description: 'Severe Delays',
      reason: 'Signalling problem',
      created_at: '2025-01-01T09:00:00Z',
      affected_routes: [
        {
          name: 'Victoria Line',
          direction: 'southbound',
          affected_stations: ['Walthamstow Central', 'Brixton'],
        },
      ],
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getDisruptions).mockResolvedValue(mockDisruptionsResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch disruptions on mount', async () => {
      const { result, unmount } = renderHook(() => useDisruptions())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.disruptions).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.error).toBeNull()
      expect(api.getDisruptions).toHaveBeenCalledTimes(1)

      unmount()
    })

    it('should filter out good service by default', async () => {
      const { result, unmount } = renderHook(() => useDisruptions())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Should filter out Northern Line (severity 10 = Good Service)
      expect(result.current.disruptions).toHaveLength(2)
      expect(result.current.disruptions?.map((d) => d.line_id)).toEqual(['piccadilly', 'victoria'])

      unmount()
    })

    it('should include good service when filterGoodService is false', async () => {
      const { result, unmount } = renderHook(() => useDisruptions({ filterGoodService: false }))

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Should include all disruptions including Northern Line
      expect(result.current.disruptions).toHaveLength(3)
      expect(result.current.disruptions?.map((d) => d.line_id)).toEqual([
        'piccadilly',
        'northern',
        'victoria',
      ])

      unmount()
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getDisruptions).mockRejectedValue(mockError)

      const { result, unmount } = renderHook(() => useDisruptions())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.disruptions).toBeNull()
      expect(result.current.error).toEqual(mockError)

      unmount()
    })

    it('should not fetch when disabled', () => {
      const { unmount } = renderHook(() => useDisruptions({ enabled: false }))

      expect(api.getDisruptions).not.toHaveBeenCalled()

      unmount()
    })
  })

  describe('refresh', () => {
    it('should manually refresh disruptions', async () => {
      const { result, unmount } = renderHook(() => useDisruptions())

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getDisruptions).toHaveBeenCalledTimes(1)

      // Manually refresh
      await act(async () => {
        await result.current.refresh()
      })

      expect(api.getDisruptions).toHaveBeenCalledTimes(2)

      unmount()
    })

    it('should handle refresh error', async () => {
      const { result, unmount } = renderHook(() => useDisruptions())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Mock error for refresh
      const mockError = new ApiError(503, 'Service Unavailable')
      vi.mocked(api.getDisruptions).mockRejectedValueOnce(mockError)

      // Refresh sets error state without throwing
      await act(async () => {
        await result.current.refresh()
      })

      expect(result.current.error).toEqual(mockError)

      unmount()
    })
  })
})
