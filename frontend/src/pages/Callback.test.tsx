import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Callback from './Callback'
import { ApiError } from '@/lib/api'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useBackendAuth hook
vi.mock('@/contexts/BackendAuthContext', () => ({
  useBackendAuth: vi.fn(),
}))

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
import { useBackendAuth } from '@/contexts/BackendAuthContext'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseBackendAuth = useBackendAuth as ReturnType<typeof vi.fn>

describe('Callback', () => {
  const mockLogout = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading spinner while authenticating', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: true,
      user: null,
      error: null,
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      isValidating: false,
      user: { id: 'test-user-id', created_at: '2025-01-01', updated_at: '2025-01-01' },
      error: null,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('should redirect to login when authentication fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: new Error('Authentication failed'),
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: null,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith('Auth0 error:', expect.any(Error))
      expect(mockLogout).toHaveBeenCalled()
    })

    consoleErrorSpy.mockRestore()
  })

  it('should show error message when authentication fails', () => {
    const authError = new Error('Authentication failed')
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: authError,
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: null,
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: true,
      user: null,
      error: null,
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: true,
      user: null,
      error: null,
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      isValidating: false,
      user: { id: 'test-user-id', created_at: '2025-01-01', updated_at: '2025-01-01' },
      error: null,
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: new ApiError(401, 'Unauthorized'),
    })

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
        expect(mockLogout).toHaveBeenCalled()
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: new ApiError(500, 'Internal Server Error'),
    })

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
        expect(mockLogout).toHaveBeenCalled()
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
      logout: mockLogout,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      isValidating: false,
      user: null,
      error: new Error('Network error'),
    })

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
        expect(mockLogout).toHaveBeenCalled()
      },
      { timeout: 2500 }
    )

    consoleErrorSpy.mockRestore()
  })
})
