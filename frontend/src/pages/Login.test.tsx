import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import Login from './Login'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
  })),
}))

describe('Login', () => {
  it('should render login page with branding', () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    )

    expect(screen.getByText('TfL Alerts')).toBeInTheDocument()
    expect(screen.getByText('Never miss a tube disruption again')).toBeInTheDocument()
  })

  it('should show sign in button', () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    )

    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('should show feature highlights', () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    )

    expect(screen.getByText('Create Routes')).toBeInTheDocument()
    expect(screen.getByText('Get Alerts')).toBeInTheDocument()
    expect(screen.getByText('Live Updates')).toBeInTheDocument()
    expect(screen.getByText('Secure')).toBeInTheDocument()
  })
})
