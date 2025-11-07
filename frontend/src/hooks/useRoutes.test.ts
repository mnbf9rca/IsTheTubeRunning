import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRoutes } from './useRoutes'
import { ApiError } from '../lib/api'
import type { RouteListItemResponse, RouteResponse } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getRoutes: vi.fn(),
    getRoute: vi.fn(),
    createRoute: vi.fn(),
    updateRoute: vi.fn(),
    deleteRoute: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useRoutes', () => {
  const mockRoutesResponse: RouteListItemResponse[] = [
    {
      id: 'route-1',
      name: 'Home to Work',
      description: 'Daily commute',
      active: true,
      timezone: 'Europe/London',
      segment_count: 3,
      schedule_count: 2,
    },
    {
      id: 'route-2',
      name: 'Weekend Route',
      description: null,
      active: false,
      timezone: 'Europe/London',
      segment_count: 2,
      schedule_count: 1,
    },
  ]

  const mockRouteResponse: RouteResponse = {
    id: 'route-1',
    name: 'Home to Work',
    description: 'Daily commute',
    active: true,
    timezone: 'Europe/London',
    segments: [],
    schedules: [],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getRoutes).mockResolvedValue(mockRoutesResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch routes on mount', async () => {
      const { result } = renderHook(() => useRoutes())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.routes).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.routes).toEqual(mockRoutesResponse)
      expect(result.current.error).toBeNull()
      expect(api.getRoutes).toHaveBeenCalledTimes(1)
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getRoutes).mockRejectedValue(mockError)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.routes).toBeNull()
      expect(result.current.error).toEqual(mockError)
    })
  })

  describe('createRoute', () => {
    it('should create route and refresh routes list', async () => {
      const newRoute: RouteResponse = {
        id: 'route-3',
        name: 'New Route',
        description: 'Test route',
        active: true,
        timezone: 'Europe/London',
        segments: [],
        schedules: [],
      }

      vi.mocked(api.createRoute).mockResolvedValue(newRoute)
      vi.mocked(api.getRoutes).mockResolvedValue([...mockRoutesResponse, newRoute])

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call createRoute
      const createData = { name: 'New Route', description: 'Test route', active: true }
      const createdRoute = await result.current.createRoute(createData)

      expect(createdRoute).toEqual(newRoute)
      expect(api.createRoute).toHaveBeenCalledWith(createData)
      // Refresh should be called
      await waitFor(() => {
        expect(api.getRoutes).toHaveBeenCalledTimes(2) // Initial + refresh
      })
    })

    it('should handle create error', async () => {
      const mockError = new ApiError(400, 'Bad Request')
      vi.mocked(api.createRoute).mockRejectedValue(mockError)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call createRoute and expect it to throw
      await expect(result.current.createRoute({ name: 'Test' })).rejects.toThrow()

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('updateRoute', () => {
    it('should update route and refresh routes list', async () => {
      const updatedRoute: RouteResponse = {
        ...mockRouteResponse,
        name: 'Updated Name',
      }

      vi.mocked(api.updateRoute).mockResolvedValue(updatedRoute)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call updateRoute
      const updateData = { name: 'Updated Name' }
      const updated = await result.current.updateRoute('route-1', updateData)

      expect(updated).toEqual(updatedRoute)
      expect(api.updateRoute).toHaveBeenCalledWith('route-1', updateData)
      // Refresh should be called
      await waitFor(() => {
        expect(api.getRoutes).toHaveBeenCalledTimes(2) // Initial + refresh
      })
    })

    it('should handle update error', async () => {
      const mockError = new ApiError(404, 'Not Found')
      vi.mocked(api.updateRoute).mockRejectedValue(mockError)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call updateRoute and expect it to throw
      await expect(result.current.updateRoute('route-1', { name: 'Test' })).rejects.toThrow()

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('deleteRoute', () => {
    it('should delete route and refresh routes list', async () => {
      vi.mocked(api.deleteRoute).mockResolvedValue()

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call deleteRoute
      await result.current.deleteRoute('route-1')

      expect(api.deleteRoute).toHaveBeenCalledWith('route-1')
      // Refresh should be called
      await waitFor(() => {
        expect(api.getRoutes).toHaveBeenCalledTimes(2) // Initial + refresh
      })
    })

    it('should handle delete error', async () => {
      const mockError = new ApiError(404, 'Not Found')
      vi.mocked(api.deleteRoute).mockRejectedValue(mockError)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call deleteRoute and expect it to throw
      await expect(result.current.deleteRoute('route-1')).rejects.toThrow()

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('getRoute', () => {
    it('should fetch single route details', async () => {
      vi.mocked(api.getRoute).mockResolvedValue(mockRouteResponse)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call getRoute
      const route = await result.current.getRoute('route-1')

      expect(route).toEqual(mockRouteResponse)
      expect(api.getRoute).toHaveBeenCalledWith('route-1')
    })

    it('should handle getRoute error', async () => {
      const mockError = new ApiError(404, 'Not Found')
      vi.mocked(api.getRoute).mockRejectedValue(mockError)

      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call getRoute and expect it to throw
      await expect(result.current.getRoute('route-1')).rejects.toThrow()

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('refresh', () => {
    it('should manually refresh routes list', async () => {
      const { result } = renderHook(() => useRoutes())

      await waitFor(() => expect(result.current.loading).toBe(false))

      // Call refresh
      await result.current.refresh()

      await waitFor(() => {
        expect(api.getRoutes).toHaveBeenCalledTimes(2) // Initial + manual refresh
      })
    })
  })
})
