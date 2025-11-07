import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useBackendAvailability } from './useBackendAvailability'
import { BackendAvailabilityProvider } from '@/contexts/BackendAvailabilityContext'

// Mock fetch
global.fetch = vi.fn()

describe('useBackendAvailability', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Use fake timers to prevent real intervals from running
    vi.useFakeTimers()
  })

  afterEach(() => {
    // Restore real timers and clear all pending timers
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('should throw error when used outside BackendAvailabilityProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      renderHook(() => useBackendAvailability())
    }).toThrow('useBackendAvailability must be used within a BackendAvailabilityProvider')

    consoleSpy.mockRestore()
  })

  it('should return context value when used within BackendAvailabilityProvider', async () => {
    // Use real timers for this test since we need to wait for async operations
    vi.useRealTimers()

    // Mock successful backend response
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ ready: true }),
    })

    const { result, unmount } = renderHook(() => useBackendAvailability(), {
      wrapper: BackendAvailabilityProvider,
    })

    expect(result.current).toBeDefined()
    expect(result.current.isChecking).toBe(true)
    expect(result.current.lastChecked).toBe(null)
    expect(typeof result.current.checkAvailability).toBe('function')

    // Wait for initial check to complete
    await waitFor(() => {
      expect(result.current.isChecking).toBe(false)
    })

    expect(result.current.isAvailable).toBe(true)
    expect(result.current.lastChecked).toBeInstanceOf(Date)

    // Explicitly unmount to clean up intervals BEFORE test ends
    unmount()

    // Give cleanup time to complete
    await new Promise((resolve) => setTimeout(resolve, 10))

    // Restore fake timers for next test
    vi.useFakeTimers()
  })
})
