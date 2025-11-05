import { renderHook } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuth } from './useAuth'
import type { User } from '@auth0/auth0-react'

// Mock Auth0
vi.mock('@auth0/auth0-react', () => ({
  useAuth0: () => ({
    user: {
      sub: 'auth0|123',
      name: 'Test User',
      email: 'test@example.com',
      picture: 'https://example.com/avatar.jpg',
    } as User,
    isAuthenticated: true,
    isLoading: false,
    error: undefined,
    loginWithRedirect: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn().mockResolvedValue('mock-token'),
  }),
}))

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should return user information when authenticated', () => {
    const { result } = renderHook(() => useAuth())

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toBeDefined()
    expect(result.current.user?.email).toBe('test@example.com')
  })

  it('should provide login function', async () => {
    const { result } = renderHook(() => useAuth())

    await result.current.login()

    // Login function should be callable
    expect(result.current.login).toBeInstanceOf(Function)
  })

  it('should provide logout function', () => {
    const { result } = renderHook(() => useAuth())

    result.current.logout()

    // Logout function should be callable
    expect(result.current.logout).toBeInstanceOf(Function)
  })

  it('should provide getAccessToken function', async () => {
    const { result } = renderHook(() => useAuth())

    const token = await result.current.getAccessToken()

    expect(token).toBe('mock-token')
  })

  it('should not be loading when auth is complete', () => {
    const { result } = renderHook(() => useAuth())

    expect(result.current.isLoading).toBe(false)
  })
})
