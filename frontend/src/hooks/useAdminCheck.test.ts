import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAdminCheck } from './useAdminCheck'

// Mock the BackendAuthContext
const mockUseBackendAuth = vi.fn()

vi.mock('@/contexts/BackendAuthContext', () => ({
  useBackendAuth: () => mockUseBackendAuth(),
}))

describe('useAdminCheck', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return isAdmin=true for authenticated admin users', () => {
    mockUseBackendAuth.mockReturnValue({
      user: { id: '123', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: true },
      isBackendAuthenticated: true,
      isValidating: false,
    })

    const { result } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(true)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.user).toBeDefined()
    expect(result.current.user?.is_admin).toBe(true)
  })

  it('should return isAdmin=false for authenticated non-admin users', () => {
    mockUseBackendAuth.mockReturnValue({
      user: { id: '123', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: false },
      isBackendAuthenticated: true,
      isValidating: false,
    })

    const { result } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.user).toBeDefined()
    expect(result.current.user?.is_admin).toBe(false)
  })

  it('should return isAdmin=false when not authenticated', () => {
    mockUseBackendAuth.mockReturnValue({
      user: null,
      isBackendAuthenticated: false,
      isValidating: false,
    })

    const { result } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isLoading).toBe(false)
    expect(result.current.user).toBe(null)
  })

  it('should return isLoading=true during validation', () => {
    mockUseBackendAuth.mockReturnValue({
      user: null,
      isBackendAuthenticated: false,
      isValidating: true,
    })

    const { result } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isLoading).toBe(true)
  })

  it('should return isAdmin=false when user is missing is_admin field', () => {
    mockUseBackendAuth.mockReturnValue({
      user: { id: '123', created_at: '2024-01-01', updated_at: '2024-01-01' },
      isBackendAuthenticated: true,
      isValidating: false,
    })

    const { result } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isLoading).toBe(false)
  })

  it('should update isAdmin when user changes from non-admin to admin', () => {
    mockUseBackendAuth.mockReturnValue({
      user: { id: '123', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: false },
      isBackendAuthenticated: true,
      isValidating: false,
    })

    const { result, rerender } = renderHook(() => useAdminCheck())

    expect(result.current.isAdmin).toBe(false)

    // Simulate user becoming admin
    mockUseBackendAuth.mockReturnValue({
      user: { id: '123', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: true },
      isBackendAuthenticated: true,
      isValidating: false,
    })

    rerender()

    expect(result.current.isAdmin).toBe(true)
  })
})
