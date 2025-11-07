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
  const mockValidateWithBackend = vi.fn()
  const mockForceLogout = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading spinner while Auth0 is loading', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
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

  it('should redirect to dashboard when already backend authenticated', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
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

  it('should show error when Auth0 authentication fails', () => {
    const authError = new Error('Authentication failed')
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: authError,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // The error message is displayed in the alert
    expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    expect(screen.getByText(/Authentication failed:/)).toBeInTheDocument()
  })

  it('should not redirect while still loading', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('should redirect to login when not authenticated with Auth0', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login')
    })
  })

  it('should show verifying state when validating with backend', async () => {
    // Mock validateWithBackend to never resolve (simulating in-progress validation)
    mockValidateWithBackend.mockImplementation(() => new Promise(() => {}))

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // Validation should be triggered and show verifying message
    await waitFor(() => {
      expect(mockValidateWithBackend).toHaveBeenCalled()
    })

    expect(screen.getByText('Verifying with server...')).toBeInTheDocument()
  })

  it('should handle backend 401 error with force logout', async () => {
    // Mock validateWithBackend to reject with 401 error
    mockValidateWithBackend.mockRejectedValueOnce(new ApiError(401, 'Unauthorized'))

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    })

    expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()

    // Should NOT have retry button (force logout instead)
    expect(screen.queryByText('Retry')).not.toBeInTheDocument()
  })

  it('should handle backend 403 error with force logout', async () => {
    // Mock validateWithBackend to reject with 403 error
    mockValidateWithBackend.mockRejectedValueOnce(new ApiError(403, 'Forbidden'))

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    })

    expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()
  })

  it('should handle backend 500 error with retry option', async () => {
    // Mock validateWithBackend to reject with 500 error
    mockValidateWithBackend.mockRejectedValueOnce(new ApiError(500, 'Internal Server Error'))

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument()
    })

    expect(screen.getByText('Server error (500). Please try again.')).toBeInTheDocument()

    // Should have retry and back to login buttons
    expect(screen.getByText('Retry')).toBeInTheDocument()
    expect(screen.getByText('Back to Login')).toBeInTheDocument()
  })

  it('should handle network error with retry option', async () => {
    // Mock validateWithBackend to reject with network error (not ApiError)
    mockValidateWithBackend.mockRejectedValueOnce(new Error('Network error'))

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      error: undefined,
    })
    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: false,
      validateWithBackend: mockValidateWithBackend,
      forceLogout: mockForceLogout,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    // Wait for error state to appear
    await waitFor(() => {
      expect(screen.getByText('Connection Error')).toBeInTheDocument()
    })

    expect(
      screen.getByText('Unable to connect to server. Please check your connection.')
    ).toBeInTheDocument()

    // Should have retry and back to login buttons
    expect(screen.getByText('Retry')).toBeInTheDocument()
    expect(screen.getByText('Back to Login')).toBeInTheDocument()
  })
})
