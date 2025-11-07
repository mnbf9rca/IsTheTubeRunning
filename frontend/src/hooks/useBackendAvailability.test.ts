import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBackendAvailability } from './useBackendAvailability'
import { BackendAvailabilityProvider } from '@/contexts/BackendAvailabilityContext'

// Mock fetch
global.fetch = vi.fn()

describe('useBackendAvailability', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    // Mock successful backend response
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({ ready: true }),
    })

    const { result } = renderHook(() => useBackendAvailability(), {
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
  })
})
