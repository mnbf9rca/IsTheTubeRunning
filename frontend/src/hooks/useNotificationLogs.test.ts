import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNotificationLogs } from './useNotificationLogs'
import { ApiError } from '../lib/api'
import type { RecentLogsResponse } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getRecentLogs: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useNotificationLogs', () => {
  const mockLogsResponse: RecentLogsResponse = {
    total: 100,
    logs: [
      {
        id: 'log-1',
        user_id: 'user-1',
        route_id: 'route-1',
        route_name: 'Test Route 1',
        sent_at: '2025-01-01T10:00:00Z',
        method: 'email',
        status: 'sent',
        error_message: null,
      },
      {
        id: 'log-2',
        user_id: 'user-2',
        route_id: 'route-2',
        route_name: 'Test Route 2',
        sent_at: '2025-01-01T11:00:00Z',
        method: 'sms',
        status: 'failed',
        error_message: 'SMS service unavailable',
      },
    ],
    limit: 50,
    offset: 0,
  }

  const mockEmptyResponse: RecentLogsResponse = {
    total: 0,
    logs: [],
    limit: 50,
    offset: 0,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getRecentLogs).mockResolvedValue(mockLogsResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch logs on mount', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.logs).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.logs).toEqual(mockLogsResponse)
      expect(result.current.error).toBeNull()
      expect(api.getRecentLogs).toHaveBeenCalledTimes(1)
      expect(api.getRecentLogs).toHaveBeenCalledWith({
        limit: 50,
        offset: 0,
        status: undefined,
      })
    })

    it('should initialize with correct default values', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.currentPage).toBe(1)
      expect(result.current.pageSize).toBe(50)
      expect(result.current.statusFilter).toBe('all')
      expect(result.current.totalLogs).toBe(100)
      expect(result.current.totalPages).toBe(2) // 100 logs / 50 per page
    })

    it('should handle API errors gracefully', async () => {
      const mockError = new ApiError('Failed to fetch logs', 500)
      vi.mocked(api.getRecentLogs).mockRejectedValue(mockError)

      // Suppress console errors for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.error).toEqual(mockError)
      expect(result.current.logs).toBeNull()

      consoleSpy.mockRestore()
    })

    it('should handle empty logs correctly', async () => {
      vi.mocked(api.getRecentLogs).mockResolvedValue(mockEmptyResponse)

      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.logs).toEqual(mockEmptyResponse)
      expect(result.current.totalLogs).toBe(0)
      expect(result.current.totalPages).toBe(0)
    })
  })

  describe('pagination', () => {
    it('should change page and refetch logs', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(2)
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 50, // (page 2 - 1) * 50
        status: undefined,
      })
      expect(result.current.currentPage).toBe(2)
    })

    it('should not allow page number less than 1', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Try to set page to 0
      act(() => {
        result.current.setPage(0)
      })

      expect(result.current.currentPage).toBe(1)
    })

    it('should not allow page number greater than total pages', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Try to set page to 999 (total pages is 2)
      act(() => {
        result.current.setPage(999)
      })

      expect(result.current.currentPage).toBe(2) // Clamped to max page
    })

    it('should change page size and reset to page 1', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change page to 2 first
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(2)
      })

      // Change page size
      act(() => {
        result.current.setPageSize(25)
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(3)
      })

      expect(result.current.currentPage).toBe(1) // Reset to page 1
      expect(result.current.pageSize).toBe(25)
      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 25,
        offset: 0,
        status: undefined,
      })
    })

    it('should calculate total pages correctly', async () => {
      const responseWith125Logs: RecentLogsResponse = {
        ...mockLogsResponse,
        total: 125,
      }
      vi.mocked(api.getRecentLogs).mockResolvedValue(responseWith125Logs)

      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // 125 logs / 50 per page = 2.5 → ceil = 3 pages
      expect(result.current.totalPages).toBe(3)
    })
  })

  describe('status filter', () => {
    it('should filter by sent status', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Set filter to 'sent'
      act(() => {
        result.current.setStatusFilter('sent')
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(2)
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: 'sent',
      })
      expect(result.current.statusFilter).toBe('sent')
    })

    it('should filter by failed status', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Set filter to 'failed'
      act(() => {
        result.current.setStatusFilter('failed')
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(2)
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: 'failed',
      })
      expect(result.current.statusFilter).toBe('failed')
    })

    it('should filter by pending status', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Set filter to 'pending'
      act(() => {
        result.current.setStatusFilter('pending')
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(2)
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: 'pending',
      })
      expect(result.current.statusFilter).toBe('pending')
    })

    it('should show all logs when filter is "all"', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Set filter to 'sent' first
      act(() => {
        result.current.setStatusFilter('sent')
      })

      await waitFor(() => {
        expect(result.current.statusFilter).toBe('sent')
      })

      // Change back to 'all'
      act(() => {
        result.current.setStatusFilter('all')
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(3)
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: undefined, // 'all' should pass undefined
      })
      expect(result.current.statusFilter).toBe('all')
    })

    it('should reset to page 1 when changing filter', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change to page 2
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(2)
      })

      // Change filter
      act(() => {
        result.current.setStatusFilter('failed')
      })

      await waitFor(() => {
        expect(api.getRecentLogs).toHaveBeenCalledTimes(3)
      })

      expect(result.current.currentPage).toBe(1) // Reset to page 1
      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: 'failed',
      })
    })
  })

  describe('refresh functionality', () => {
    it('should refetch logs when refresh is called', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getRecentLogs).toHaveBeenCalledTimes(1)

      // Call refresh
      await act(async () => {
        await result.current.refresh()
      })

      expect(api.getRecentLogs).toHaveBeenCalledTimes(2)
      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: undefined,
      })
    })

    it('should refresh with current filters and pagination', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change page first (this will trigger a refetch)
      act(() => {
        result.current.setPage(2)
      })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Now change filter (this will trigger another refetch and reset to page 1)
      act(() => {
        result.current.setStatusFilter('sent')
      })

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Call refresh - should use current state (page 1 after filter change, status 'sent')
      await act(async () => {
        await result.current.refresh()
      })

      // After filter change, page should be 1, status should be 'sent'
      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 50,
        offset: 0,
        status: 'sent',
      })
    })
  })

  describe('combined filters and pagination', () => {
    it('should handle multiple filter and pagination changes', async () => {
      const { result } = renderHook(() => useNotificationLogs())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Change page size
      act(() => {
        result.current.setPageSize(25)
      })

      await waitFor(() => {
        expect(result.current.pageSize).toBe(25)
      })

      // Change page
      act(() => {
        result.current.setPage(3)
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(3)
      })

      // Change filter
      act(() => {
        result.current.setStatusFilter('failed')
      })

      await waitFor(() => {
        expect(result.current.currentPage).toBe(1) // Reset
      })

      expect(api.getRecentLogs).toHaveBeenLastCalledWith({
        limit: 25,
        offset: 0, // Page 1 after filter change
        status: 'failed',
      })
    })
  })
})
