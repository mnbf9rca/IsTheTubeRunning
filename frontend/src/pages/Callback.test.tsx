import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Callback from './Callback'
import { ApiError } from '@/lib/api'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock API module
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    getCurrentUser: vi.fn(),
  }
})

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import { useAuth } from '@/hooks/useAuth'
import * as api from '@/lib/api'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>

describe('Callback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading spinner while authenticating', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Completing sign in...')).toBeInTheDocument()

    // Check for loading spinner
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('should redirect to dashboard when authenticated', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })

    // Mock successful backend validation
    vi.mocked(api.getCurrentUser).mockResolvedValue({
      id: 'test-user-id',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(api.getCurrentUser).toHaveBeenCalled()
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('should redirect to login when authentication fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: new Error('Authentication failed'),
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith('Auth0 error:', expect.any(Error))
      expect(mockNavigate).toHaveBeenCalledWith('/login')
    })

    consoleErrorSpy.mockRestore()
  })

  it('should show error message when authentication fails', () => {
    const authError = new Error('Authentication failed')
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: authError,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // The error message is displayed
    expect(screen.getByText('Authentication failed')).toBeInTheDocument()
  })

  it('should not redirect while still loading', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('should handle rapid state changes correctly', async () => {
    // Start with loading
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
    })

    // Mock successful backend validation
    vi.mocked(api.getCurrentUser).mockResolvedValue({
      id: 'test-user-id',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    })

    const { rerender } = render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(mockNavigate).not.toHaveBeenCalled()

    // Become authenticated
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })

    rerender(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
      expect(mockNavigate).toHaveBeenCalledTimes(1)
    })
  })

  it('should handle backend 401 error and redirect to login', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })

    // Mock backend validation failure (invalid token)
    vi.mocked(api.getCurrentUser).mockRejectedValue(new ApiError(401, 'Unauthorized'))

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Authentication failed. Please try again.')).toBeInTheDocument()
    })

    // Wait for timeout redirect
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/login')
      },
      { timeout: 2500 }
    )

    consoleErrorSpy.mockRestore()
  })

  it('should handle backend 500 error and redirect to login', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })

    // Mock backend server error
    vi.mocked(api.getCurrentUser).mockRejectedValue(new ApiError(500, 'Internal Server Error'))

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Server error. Please try again later.')).toBeInTheDocument()
    })

    // Wait for timeout redirect
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/login')
      },
      { timeout: 2500 }
    )

    consoleErrorSpy.mockRestore()
  })

  it('should handle backend unavailable and redirect to login', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })

    // Mock network error (backend not running)
    vi.mocked(api.getCurrentUser).mockRejectedValue(new Error('Network error'))

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(
        screen.getByText('Backend unavailable. Please ensure the server is running.')
      ).toBeInTheDocument()
    })

    // Wait for timeout redirect
    await waitFor(
      () => {
        expect(mockNavigate).toHaveBeenCalledWith('/login')
      },
      { timeout: 2500 }
    )

    consoleErrorSpy.mockRestore()
  })
})
