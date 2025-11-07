import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'

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
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      isValidating: false,
      user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      error: null,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should show loading state when loading', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: true,
      user: null,
      error: null,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Authenticating...')).toBeInTheDocument()
  })

  it('should redirect to login when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: null,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    // Content should not be visible
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })
})
