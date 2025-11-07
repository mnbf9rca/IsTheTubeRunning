import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useBackendAuth } from './useBackendAuth'
import { BackendAuthProvider } from '@/contexts/BackendAuthContext'

// Mock dependencies
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
  }),
}))

vi.mock('@/lib/api', () => ({
  getCurrentUser: vi.fn(),
}))

describe('useBackendAuth', () => {
  it('should throw error when used outside BackendAuthProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      renderHook(() => useBackendAuth())
    }).toThrow('useBackendAuth must be used within a BackendAuthProvider')

    consoleSpy.mockRestore()
  })

  it('should return context value when used within BackendAuthProvider', () => {
    const { result } = renderHook(() => useBackendAuth(), {
      wrapper: BackendAuthProvider,
    })

    expect(result.current).toBeDefined()
    expect(result.current.user).toBe(null)
    expect(result.current.isBackendAuthenticated).toBe(false)
    expect(result.current.isValidating).toBe(false)
    expect(result.current.error).toBe(null)
    expect(typeof result.current.validateWithBackend).toBe('function')
    expect(typeof result.current.clearAuth).toBe('function')
    expect(typeof result.current.forceLogout).toBe('function')
  })
})
