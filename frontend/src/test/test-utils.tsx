import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'

interface BackendUser {
  id: string
  created_at: string
  updated_at: string
  is_admin: boolean
}

/**
 * Helper function to create mock return values for useBackendAuth hook
 * This reduces duplication and ensures consistency across test files
 *
 * @example
 * ```ts
 * const mockValidateWithBackend = vi.fn()
 * const mockForceLogout = vi.fn()
 *
 * mockUseBackendAuth.mockReturnValue(
 *   createMockBackendAuth({
 *     validateWithBackend: mockValidateWithBackend,
 *     forceLogout: mockForceLogout,
 *     isBackendAuthenticated: true,
 *   })
 * )
 * ```
 */
export function createMockBackendAuth(
  overrides?: Partial<{
    isBackendAuthenticated: boolean
    user: BackendUser | null
    isValidating: boolean
    error: Error | null
    validateWithBackend: () => Promise<void>
    forceLogout: () => void
    clearAuth: () => void
  }>
) {
  return {
    isBackendAuthenticated: false,
    user: null,
    isValidating: false,
    error: null,
    validateWithBackend: vi.fn(),
    forceLogout: vi.fn(),
    clearAuth: vi.fn(),
    ...overrides,
  }
}

/**
 * Helper function to create mock return values for useAuth hook
 * This reduces duplication and ensures consistency across test files
 *
 * @example
 * ```ts
 * mockUseAuth.mockReturnValue(
 *   createMockAuth({
 *     isAuthenticated: true,
 *     user: { name: 'Test User' },
 *   })
 * )
 * ```
 */
export function createMockAuth(
  overrides?: Partial<{
    isAuthenticated: boolean
    isLoading: boolean
    user: unknown
    error: Error | undefined
    login: () => void
    logout: () => void
    getAccessToken: () => Promise<string>
  }>
) {
  return {
    isAuthenticated: false,
    isLoading: false,
    user: null,
    error: undefined,
    login: vi.fn(),
    logout: vi.fn(),
    getAccessToken: vi.fn(),
    ...overrides,
  }
}

/**
 * Custom render function that wraps components in MemoryRouter
 * Use this for components that use React Router hooks (useNavigate, useParams, etc.)
 *
 * @example
 * ```tsx
 * renderWithRouter(<MyComponent />)
 * renderWithRouter(<MyComponent />, { route: '/my-route' })
 * ```
 */
export function renderWithRouter(
  ui: React.ReactElement,
  { route = '/', ...renderOptions }: { route?: string } & Parameters<typeof render>[1] = {}
) {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>, renderOptions)
}

// Re-export everything from React Testing Library for convenience
// eslint-disable-next-line react-refresh/only-export-components
export * from '@testing-library/react'
