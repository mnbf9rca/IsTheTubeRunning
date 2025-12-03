import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePolling } from './usePolling'
import type { ReactNode } from 'react'
import { PollingProvider } from '@/contexts/PollingContext'
import * as BackendAvailabilityHook from '@/hooks/useBackendAvailability'
import * as BackendAuthHook from '@/hooks/useBackendAuth'

// Mock the hooks
vi.mock('@/hooks/useBackendAvailability')
vi.mock('@/hooks/useBackendAuth')

describe('usePolling', () => {
  const mockUseBackendAvailability = vi.mocked(BackendAvailabilityHook.useBackendAvailability)
  const mockUseBackendAuth = vi.mocked(BackendAuthHook.useBackendAuth)

  beforeEach(() => {
    // Default mocks
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
    vi.clearAllMocks()
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <PollingProvider>{children}</PollingProvider>
  )

  describe('initial data loading', () => {
    it('should start with loading state', () => {
      const fetchFn = vi.fn().mockImplementation(() => new Promise(() => {})) // Never resolves

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000, // Long interval to avoid auto-refresh during test
          }),
        { wrapper }
      )

      expect(result.current.loading).toBe(true)
      expect(result.current.data).toBeNull()
      expect(result.current.error).toBeNull()
    })

    it('should fetch and set data on mount', async () => {
      const testData = { value: 'test-data' }
      const fetchFn = vi.fn().mockResolvedValue(testData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.data).toEqual(testData)
      expect(result.current.error).toBeNull()
      expect(result.current.lastUpdated).toBeInstanceOf(Date)
      expect(fetchFn).toHaveBeenCalled()
    })

    it('should set error on fetch failure', async () => {
      const testError = new Error('Fetch failed')
      const fetchFn = vi.fn().mockRejectedValue(testError)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.data).toBeNull()
      expect(result.current.error).toEqual(testError)
      expect(result.current.lastUpdated).toBeNull()
    })
  })

  describe('manual refresh', () => {
    it('should allow manual refresh', async () => {
      const testData = { value: 'test-data' }
      const fetchFn = vi.fn().mockResolvedValue(testData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const callCount = fetchFn.mock.calls.length

      // Manual refresh
      await result.current.refresh()

      expect(fetchFn).toHaveBeenCalledTimes(callCount + 1)
    })

    it('should update data on manual refresh', async () => {
      const firstData = { value: 'first' }
      const secondData = { value: 'second' }
      const fetchFn = vi.fn().mockResolvedValueOnce(firstData).mockResolvedValueOnce(secondData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.data).toEqual(firstData)
      })

      // Manual refresh
      await result.current.refresh()

      await waitFor(() => {
        expect(result.current.data).toEqual(secondData)
      })
    })

    it('should use isRefreshing for background updates', async () => {
      const testData = { value: 'test-data' }
      const fetchFn = vi
        .fn()
        .mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve(testData), 50)))

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      // Wait for initial load
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.isRefreshing).toBe(false)

      // Trigger manual refresh
      const refreshPromise = result.current.refresh()

      // Should show refreshing but not loading
      await waitFor(() => {
        expect(result.current.isRefreshing).toBe(true)
      })

      expect(result.current.loading).toBe(false)
      expect(result.current.data).toEqual(testData) // Previous data still available

      // Wait for refresh to complete
      await refreshPromise

      await waitFor(() => {
        expect(result.current.isRefreshing).toBe(false)
      })
    })
  })

  describe('data transformation', () => {
    it('should apply transformation function', async () => {
      const rawData = { value: 'test' }
      const transform = vi.fn((data: typeof rawData) => ({
        value: data.value.toUpperCase(),
      }))
      const fetchFn = vi.fn().mockResolvedValue(rawData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
            transform,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.data).toEqual({ value: 'TEST' })
      expect(transform).toHaveBeenCalledWith(rawData)
      expect(fetchFn).toHaveBeenCalled()
    })
  })

  describe('enabled/disabled state', () => {
    it('should not poll when disabled', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
            enabled: false,
          }),
        { wrapper }
      )

      // Wait a bit
      await new Promise((resolve) => setTimeout(resolve, 50))

      expect(result.current.loading).toBe(false)
      expect(fetchFn).not.toHaveBeenCalled()
    })

    it('should start polling when enabled is changed to true', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      const { rerender } = renderHook(
        ({ enabled }) =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
            enabled,
          }),
        { wrapper, initialProps: { enabled: false } }
      )

      // Should not poll when disabled
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(fetchFn).not.toHaveBeenCalled()

      // Enable polling
      rerender({ enabled: true })

      // Should start polling
      await waitFor(() => {
        expect(fetchFn).toHaveBeenCalled()
      })
    })
  })

  describe('cleanup', () => {
    it('should cleanup on unmount', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      const { result, unmount } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const callCount = fetchFn.mock.calls.length

      // Unmount
      unmount()

      // Wait a bit - should not poll after unmount
      await new Promise((resolve) => setTimeout(resolve, 50))
      expect(fetchFn).toHaveBeenCalledTimes(callCount)
    })
  })

  describe('error recovery', () => {
    it('should clear error on successful retry', async () => {
      const testData = { value: 'test-data' }
      const testError = new Error('Fetch failed')
      const fetchFn = vi.fn().mockRejectedValueOnce(testError).mockResolvedValue(testData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      // First call fails
      await waitFor(() => {
        expect(result.current.error).toEqual(testError)
      })

      // Manual refresh succeeds
      await result.current.refresh()

      await waitFor(() => {
        expect(result.current.error).toBeNull()
        expect(result.current.data).toEqual(testData)
      })
    })
  })

  describe('lastUpdated timestamp', () => {
    it('should update lastUpdated on successful fetch', async () => {
      const testData = { value: 'test-data' }
      const fetchFn = vi.fn().mockResolvedValue(testData)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      expect(result.current.lastUpdated).toBeNull()

      await waitFor(() => {
        expect(result.current.lastUpdated).toBeInstanceOf(Date)
      })

      const firstTimestamp = result.current.lastUpdated

      // Manual refresh
      await new Promise((resolve) => setTimeout(resolve, 10)) // Ensure time passes
      await result.current.refresh()

      await waitFor(() => {
        expect(result.current.lastUpdated).toBeInstanceOf(Date)
        expect(result.current.lastUpdated!.getTime()).toBeGreaterThanOrEqual(
          firstTimestamp!.getTime()
        )
      })
    })

    it('should not update lastUpdated on fetch failure', async () => {
      const testData = { value: 'test-data' }
      const testError = new Error('Fetch failed')
      const fetchFn = vi.fn().mockResolvedValueOnce(testData).mockRejectedValue(testError)

      const { result } = renderHook(
        () =>
          usePolling({
            key: 'test-poll',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      // First call succeeds
      await waitFor(() => {
        expect(result.current.lastUpdated).toBeInstanceOf(Date)
      })

      const firstTimestamp = result.current.lastUpdated

      // Second call fails
      await result.current.refresh()

      await waitFor(() => {
        expect(result.current.error).toEqual(testError)
      })

      // lastUpdated should not change
      expect(result.current.lastUpdated).toBe(firstTimestamp)
    })
  })

  describe('integration with PollingCoordinator', () => {
    it('should register with coordinator on mount', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      const { unmount } = renderHook(
        () =>
          usePolling({
            key: 'integration-test',
            fetchFn,
            interval: 100000,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(fetchFn).toHaveBeenCalled()
      })

      unmount()
    })

    it('should respect requiresAuth option', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      renderHook(
        () =>
          usePolling({
            key: 'auth-test',
            fetchFn,
            interval: 100000,
            requiresAuth: true,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(fetchFn).toHaveBeenCalled()
      })
    })

    it('should respect pauseWhenBackendDown option', async () => {
      const fetchFn = vi.fn().mockResolvedValue({ data: 'test' })

      renderHook(
        () =>
          usePolling({
            key: 'health-test',
            fetchFn,
            interval: 100000,
            pauseWhenBackendDown: true,
          }),
        { wrapper }
      )

      await waitFor(() => {
        expect(fetchFn).toHaveBeenCalled()
      })
    })
  })
})
