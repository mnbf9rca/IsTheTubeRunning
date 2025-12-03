import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useUserRouteDisruptions } from './useUserRouteDisruptions'
import { ApiError } from '../lib/api'
import type { RouteDisruptionResponse } from '@/types'
import type { ReactNode } from 'react'
import { PollingProvider } from '@/contexts/PollingContext'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getRouteDisruptions: vi.fn(),
  }
})

// Mock the backend hooks
vi.mock('@/hooks/useBackendAvailability')
vi.mock('@/hooks/useBackendAuth')

// Import mocked functions
import * as api from '../lib/api'
import * as BackendAvailabilityHook from '@/hooks/useBackendAvailability'
import * as BackendAuthHook from '@/hooks/useBackendAuth'

describe('useUserRouteDisruptions', () => {
  const mockUseBackendAvailability = vi.mocked(BackendAvailabilityHook.useBackendAvailability)
  const mockUseBackendAuth = vi.mocked(BackendAuthHook.useBackendAuth)

  const mockRouteDisruptionsResponse: RouteDisruptionResponse[] = [
    {
      route_id: 'route-1',
      route_name: 'Home to Work',
      disruption: {
        line_id: 'piccadilly',
        line_name: 'Piccadilly',
        mode: 'tube',
        status_severity: 10,
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
      affected_segments: [0, 1, 2],
      affected_stations: ['940GZZLUKSX', '940GZZLULSX'],
    },
    {
      route_id: 'route-2',
      route_name: 'Morning Commute',
      disruption: {
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
      affected_segments: [1],
      affected_stations: ['940GZZLUEUS'],
    },
  ]

  const wrapper = ({ children }: { children: ReactNode }) => (
    <PollingProvider>{children}</PollingProvider>
  )

  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock implementation
    vi.mocked(api.getRouteDisruptions).mockResolvedValue(mockRouteDisruptionsResponse)

    // Mock backend hooks
    mockUseBackendAvailability.mockReturnValue({
      isAvailable: true,
      isChecking: false,
      lastChecked: new Date(),
      checkAvailability: vi.fn(),
    })

    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      loading: false,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch route disruptions on mount', async () => {
      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.disruptions).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.disruptions).toEqual(mockRouteDisruptionsResponse)
      expect(result.current.error).toBeNull()
      expect(api.getRouteDisruptions).toHaveBeenCalledTimes(1)
      expect(api.getRouteDisruptions).toHaveBeenCalledWith(true) // activeOnly=true by default

      unmount()
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getRouteDisruptions).mockRejectedValue(mockError)

      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.disruptions).toBeNull()
      expect(result.current.error).toEqual(mockError)

      unmount()
    })

    it('should handle 503 error (TfL API unavailable)', async () => {
      const mockError = new ApiError(503, 'Service Unavailable')
      vi.mocked(api.getRouteDisruptions).mockRejectedValue(mockError)

      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.error?.status).toBe(503)

      unmount()
    })

    it('should handle empty response', async () => {
      vi.mocked(api.getRouteDisruptions).mockResolvedValue([])

      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.disruptions).toEqual([])
      expect(result.current.error).toBeNull()

      unmount()
    })

    it('should not fetch when disabled', async () => {
      const { unmount } = renderHook(() => useUserRouteDisruptions({ enabled: false }), { wrapper })

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(api.getRouteDisruptions).not.toHaveBeenCalled()

      unmount()
    })
  })

  describe('activeOnly parameter', () => {
    it('should pass activeOnly=false when specified', async () => {
      const { result, unmount } = renderHook(() => useUserRouteDisruptions({ activeOnly: false }), {
        wrapper,
      })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getRouteDisruptions).toHaveBeenCalledWith(false)

      unmount()
    })

    it('should default to activeOnly=true', async () => {
      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getRouteDisruptions).toHaveBeenCalledWith(true)

      unmount()
    })
  })

  describe('refresh', () => {
    it('should manually refresh disruptions', async () => {
      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getRouteDisruptions).toHaveBeenCalledTimes(1)

      // Manually refresh
      await act(async () => {
        await result.current.refresh()
      })

      expect(api.getRouteDisruptions).toHaveBeenCalledTimes(2)

      unmount()
    })

    it('should handle refresh error', async () => {
      const { result, unmount } = renderHook(() => useUserRouteDisruptions(), { wrapper })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Mock error for refresh
      const mockError = new ApiError(503, 'Service Unavailable')
      vi.mocked(api.getRouteDisruptions).mockRejectedValueOnce(mockError)

      // Refresh sets error state without throwing
      await act(async () => {
        await result.current.refresh()
      })

      expect(result.current.error).toEqual(mockError)

      unmount()
    })
  })
})
