import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { Header } from './Header'
import type { User } from '@auth0/auth0-react'
import { createMockAuth, createMockBackendAuth } from '@/test/test-utils'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useBackendAuth hook
vi.mock('@/contexts/BackendAuthContext', () => ({
  useBackendAuth: vi.fn(),
}))

// Mock resetAccessTokenGetter
vi.mock('@/lib/api', () => ({
  resetAccessTokenGetter: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'
import { useBackendAuth } from '@/contexts/BackendAuthContext'
import { resetAccessTokenGetter } from '@/lib/api'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseBackendAuth = useBackendAuth as ReturnType<typeof vi.fn>
const mockResetAccessTokenGetter = resetAccessTokenGetter as ReturnType<typeof vi.fn>

describe('Header', () => {
  const mockLogin = vi.fn()
  const mockLogout = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('when not authenticated', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue(
        createMockAuth({
          login: mockLogin,
          logout: mockLogout,
        })
      )
      mockUseBackendAuth.mockReturnValue(createMockBackendAuth())
    })

    it('should show login button', () => {
      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument()
    })

    it('should call login when login button is clicked', () => {
      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      fireEvent.click(screen.getByRole('button', { name: /log in/i }))
      expect(mockLogin).toHaveBeenCalled()
    })

    it('should not show navigation', () => {
      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      // Navigation should not be visible
      expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    })
  })

  describe('when loading', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue(
        createMockAuth({
          isLoading: true,
          login: mockLogin,
          logout: mockLogout,
        })
      )
      mockUseBackendAuth.mockReturnValue(createMockBackendAuth())
    })

    it('should show loading skeleton', () => {
      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      // Should show loading placeholder (animated div)
      const loadingElement = document.querySelector('.animate-pulse')
      expect(loadingElement).toBeInTheDocument()
    })
  })

  describe('when authenticated', () => {
    beforeEach(() => {
      mockUseBackendAuth.mockReturnValue(
        createMockBackendAuth({
          isBackendAuthenticated: true,
        })
      )
    })

    it('should show navigation when authenticated', () => {
      mockUseAuth.mockReturnValue(
        createMockAuth({
          user: {
            name: 'John Doe',
            email: 'john@example.com',
          } as User,
          isAuthenticated: true,
          login: mockLogin,
          logout: mockLogout,
        })
      )

      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      expect(screen.getByRole('navigation')).toBeInTheDocument()
    })

    it('should render avatar button with user initials', () => {
      mockUseAuth.mockReturnValue(
        createMockAuth({
          user: {
            name: 'John Doe',
            email: 'john@example.com',
          } as User,
          isAuthenticated: true,
          login: mockLogin,
          logout: mockLogout,
        })
      )

      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      // Avatar should show "JD"
      expect(screen.getByText('JD')).toBeInTheDocument()
    })

    it('should call handleLogout when logout is clicked', async () => {
      const user = userEvent.setup()

      mockUseAuth.mockReturnValue(
        createMockAuth({
          user: {
            name: 'John Doe',
            email: 'john@example.com',
          } as User,
          isAuthenticated: true,
          login: mockLogin,
          logout: mockLogout,
        })
      )

      render(
        <BrowserRouter>
          <Header />
        </BrowserRouter>
      )

      // Click the avatar button (find by initials)
      const initialsElement = screen.getByText('JD')
      const avatarButton = initialsElement.closest('button')
      expect(avatarButton).toBeInTheDocument()
      await user.click(avatarButton!)

      // Click logout
      const logoutItem = await screen.findByRole('menuitem', { name: /log out/i })
      await user.click(logoutItem)

      expect(mockResetAccessTokenGetter).toHaveBeenCalled()
      expect(mockLogout).toHaveBeenCalled()
    })
  })
})
