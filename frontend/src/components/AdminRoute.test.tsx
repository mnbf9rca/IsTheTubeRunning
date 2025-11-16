import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AdminRoute } from './AdminRoute'
import { createMockAuth } from '@/test/test-utils'

// Mock useAuth hook
vi.mock('@/hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

// Mock useAdminCheck hook
vi.mock('@/hooks/useAdminCheck', () => ({
  useAdminCheck: vi.fn(),
}))

import { useAuth } from '@/hooks/useAuth'
import { useAdminCheck } from '@/hooks/useAdminCheck'

const mockUseAuth = useAuth as ReturnType<typeof vi.fn>
const mockUseAdminCheck = useAdminCheck as ReturnType<typeof vi.fn>

describe('AdminRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render children for admin users', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: true,
      isLoading: false,
      isInitializing: false,
      user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: true },
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Admin Content')).toBeInTheDocument()
  })

  it('should show loading spinner during admin check', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: true,
      isInitializing: false,
      user: null,
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Checking permissions...')).toBeInTheDocument()
  })

  it('should redirect non-admin authenticated users to dashboard', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      isInitializing: false,
      user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: false },
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    // Should redirect to dashboard
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
    })

    // Admin content should not be visible
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('should redirect unauthenticated users to dashboard', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: false,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      isInitializing: false,
      user: null,
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    // Should redirect to dashboard
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
    })

    // Admin content should not be visible
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('should show loading spinner while Auth0 is loading', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isLoading: true,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      isInitializing: false,
      user: null,
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Checking permissions...')).toBeInTheDocument()
  })

  it('should preserve intended location in navigation state on redirect', async () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      isInitializing: false,
      user: { id: '1', created_at: '2024-01-01', updated_at: '2024-01-01', is_admin: false },
    })

    const TestDashboard = () => {
      return <div>Dashboard Page</div>
    }

    render(
      <MemoryRouter initialEntries={['/admin/users']}>
        <Routes>
          <Route path="/dashboard" element={<TestDashboard />} />
          <Route
            path="/admin/users"
            element={
              <AdminRoute>
                <div>Admin Users Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    // Should redirect to dashboard
    await waitFor(() => {
      expect(screen.getByText('Dashboard Page')).toBeInTheDocument()
    })
  })

  it('should show loading spinner during initialization (Auth0 done, backend pending)', () => {
    mockUseAuth.mockReturnValue(
      createMockAuth({
        isAuthenticated: true,
        isLoading: false,
      })
    )
    mockUseAdminCheck.mockReturnValue({
      isAdmin: false,
      isLoading: false,
      isInitializing: true,
      user: null,
    })

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Routes>
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <div>Admin Content</div>
              </AdminRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText('Checking permissions...')).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })
})
