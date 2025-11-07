import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'
import { createMockAuth, createMockBackendAuth } from '@/test/test-utils'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useBackendAuth hook
vi.mock('@/contexts/BackendAuthContext', () => ({
  useBackendAuth: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseBackendAuth = useBackendAuth as ReturnType<typeof vi.fn>

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render children when authenticated', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        isBackendAuthenticated: true,
        user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      })
    )

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should show loading state when loading', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        isValidating: true,
      })
    )

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Authenticating...')).toBeInTheDocument()
  })

  it('should redirect to login when not authenticated', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: false,
      })
    )
    mockUseBackendAuth.mockReturnValue(createMockBackendAuth())

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    // Should redirect to login page
    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })

    // Protected content should not be visible
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})
