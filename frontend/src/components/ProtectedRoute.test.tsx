import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

describe('ProtectedRoute', () => {
  it('should render children when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
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
      isAuthenticated: false,
      isLoading: true,
    })

    render(
      <BrowserRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </BrowserRouter>
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('should redirect to login when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
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
