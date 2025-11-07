import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Callback from './Callback'
import { createMockAuth, createMockBackendAuth } from '@/test/test-utils'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useBackendAuth hook
vi.mock('@/contexts/BackendAuthContext', () => ({
  useBackendAuth: vi.fn(),
}))

// Mock useCallbackValidation hook
vi.mock('@/hooks/useCallbackValidation', () => ({
  useCallbackValidation: vi.fn(),
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
import { useCallbackValidation } from '@/hooks/useCallbackValidation'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseBackendAuth = useBackendAuth as ReturnType<typeof vi.fn>
const mockUseCallbackValidation = useCallbackValidation as ReturnType<typeof vi.fn>

describe('Callback', () => {
  const mockValidateWithBackend = vi.fn()
  const mockForceLogout = vi.fn()
  const mockPerformValidation = vi.fn()
  const mockHandleRetry = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading spinner while Auth0 is loading', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isLoading: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'idle',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
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
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        isBackendAuthenticated: true,
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'idle',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
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
    mockUseAuth.mockReturnValue(
      createMockAuth({
        error: authError,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'idle',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
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
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isLoading: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'idle',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('should redirect to login when not authenticated with Auth0', async () => {
    mockUseAuth.mockReturnValue(createMockAuth())
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'idle',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
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
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'validating',
      errorMessage: '',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Verifying with server...')).toBeInTheDocument()
  })

  it('should handle backend 401 error with force logout', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'auth_denied',
      errorMessage: 'Authentication denied by server. Logging out...',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()

    // Should NOT have retry button (force logout instead)
    expect(screen.queryByText('Retry')).not.toBeInTheDocument()
  })

  it('should handle backend 403 error with force logout', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'auth_denied',
      errorMessage: 'Authentication denied by server. Logging out...',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    expect(screen.getByText('Authentication denied by server. Logging out...')).toBeInTheDocument()
  })

  it('should handle backend 500 error with retry option', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'server_error',
      errorMessage: 'Server error (500). Please try again.',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Connection Error')).toBeInTheDocument()
    expect(screen.getByText('Server error (500). Please try again.')).toBeInTheDocument()

    // Should have retry and back to login buttons
    expect(screen.getByText('Retry')).toBeInTheDocument()
    expect(screen.getByText('Back to Login')).toBeInTheDocument()
  })

  it('should handle network error with retry option', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseBackendAuth.mockReturnValue(
      createMockBackendAuth({
        validateWithBackend: mockValidateWithBackend,
        forceLogout: mockForceLogout,
      })
    )
    mockUseCallbackValidation.mockReturnValue({
      validationState: 'server_error',
      errorMessage: 'Unable to connect to server. Please check your connection.',
      performValidation: mockPerformValidation,
      handleRetry: mockHandleRetry,
    })

    render(
      <BrowserRouter>
        <Callback />
      </BrowserRouter>
    )

    expect(screen.getByText('Connection Error')).toBeInTheDocument()
    expect(
      screen.getByText('Unable to connect to server. Please check your connection.')
    ).toBeInTheDocument()

    // Should have retry and back to login buttons
    expect(screen.getByText('Retry')).toBeInTheDocument()
    expect(screen.getByText('Back to Login')).toBeInTheDocument()
  })
})
