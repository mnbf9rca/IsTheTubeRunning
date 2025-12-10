import { renderWithRouter, screen } from '@/test/test-utils'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Routes } from './Routes'
import { ApiError, type RouteListItemResponse } from '../lib/api'

// Mock the useRoutes hook
vi.mock('../hooks/useRoutes', () => ({
  useRoutes: vi.fn(),
}))

// Mock the useUserRouteDisruptions hook
vi.mock('../hooks/useUserRouteDisruptions', () => ({
  useUserRouteDisruptions: vi.fn(),
}))

// Mock sonner for toast notifications
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

// Mock react-router-dom navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import { useRoutes } from '../hooks/useRoutes'
import { useUserRouteDisruptions } from '../hooks/useUserRouteDisruptions'

describe('Routes', () => {
  const mockRoutes: RouteListItemResponse[] = [
    {
      id: 'route-1',
      name: 'Home to Work',
      description: 'Daily commute',
      active: true,
      timezone: 'Europe/London',
      segment_count: 3,
      schedule_count: 2,
    },
  ]

  const mockUseRoutes = {
    routes: mockRoutes,
    loading: false,
    error: null,
    createRoute: vi.fn(),
    updateRoute: vi.fn(),
    deleteRoute: vi.fn(),
    getRoute: vi.fn(),
    refresh: vi.fn(),
  }

  const mockUseUserRouteDisruptions = {
    disruptions: null,
    loading: false,
    isRefreshing: false,
    error: null,
    refresh: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useRoutes).mockReturnValue(mockUseRoutes)
    vi.mocked(useUserRouteDisruptions).mockReturnValue(mockUseUserRouteDisruptions)
    mockNavigate.mockClear()
  })

  it('should render page header', () => {
    renderWithRouter(<Routes />)

    expect(screen.getByRole('heading', { name: /routes/i })).toBeInTheDocument()
    expect(screen.getByText(/manage your commute routes/i)).toBeInTheDocument()
  })

  it('should render create route button', () => {
    renderWithRouter(<Routes />)

    const createButton = screen.getByRole('button', { name: /create route/i })
    expect(createButton).toBeInTheDocument()
  })

  it('should navigate to create route page when create button is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<Routes />)

    const createButton = screen.getByRole('button', { name: /create route/i })
    await user.click(createButton)

    // Should navigate to /routes/new
    expect(mockNavigate).toHaveBeenCalledWith('/routes/new')
  })

  it('should render loading state', () => {
    vi.mocked(useRoutes).mockReturnValue({
      ...mockUseRoutes,
      loading: true,
      routes: null,
    })

    renderWithRouter(<Routes />)

    expect(screen.getByText(/loading routes/i)).toBeInTheDocument()
  })

  it('should render error state', () => {
    const mockError = new ApiError(500, 'Internal Server Error')
    vi.mocked(useRoutes).mockReturnValue({
      ...mockUseRoutes,
      error: mockError,
    })

    renderWithRouter(<Routes />)

    expect(screen.getByText(/error/i)).toBeInTheDocument()
    expect(screen.getByText(/failed to load routes/i)).toBeInTheDocument()
  })

  it('should render auth error state', () => {
    const mockError = new ApiError(401, 'Unauthorized')
    vi.mocked(useRoutes).mockReturnValue({
      ...mockUseRoutes,
      error: mockError,
    })

    renderWithRouter(<Routes />)

    expect(screen.getByText(/your session has expired/i)).toBeInTheDocument()
  })

  it('should render routes list', () => {
    renderWithRouter(<Routes />)

    expect(screen.getByText('Home to Work')).toBeInTheDocument()
    expect(screen.getByText(/you have 1 route/i)).toBeInTheDocument()
  })

  it('should handle plural routes count', () => {
    vi.mocked(useRoutes).mockReturnValue({
      ...mockUseRoutes,
      routes: [...mockRoutes, { ...mockRoutes[0], id: 'route-2', name: 'Route 2' }],
    })

    renderWithRouter(<Routes />)

    expect(screen.getByText(/you have 2 routes/i)).toBeInTheDocument()
  })

  it('should disable create button when loading', () => {
    vi.mocked(useRoutes).mockReturnValue({
      ...mockUseRoutes,
      loading: true,
    })

    renderWithRouter(<Routes />)

    const createButton = screen.getByRole('button', { name: /create route/i })
    expect(createButton).toBeDisabled()
  })

  it('should open delete confirmation dialog when delete is clicked', async () => {
    const user = userEvent.setup()
    renderWithRouter(<Routes />)

    // Click delete button on route card
    const deleteButton = screen.getByRole('button', { name: /delete route home to work/i })
    await user.click(deleteButton)

    // Confirmation dialog should appear
    expect(screen.getByText(/delete route\?/i)).toBeInTheDocument()
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument()
  })

  describe('disruptions integration', () => {
    it('should call useUserRouteDisruptions hook', () => {
      renderWithRouter(<Routes />)

      expect(useUserRouteDisruptions).toHaveBeenCalled()
    })

    it('should show good service when no disruptions', () => {
      vi.mocked(useUserRouteDisruptions).mockReturnValue({
        ...mockUseUserRouteDisruptions,
        disruptions: null,
      })

      renderWithRouter(<Routes />)

      expect(screen.getByText('Good Service')).toBeInTheDocument()
    })

    it('should pass disruptions to RouteList', () => {
      const mockDisruptions = [
        {
          route_id: 'route-1',
          route_name: 'Home to Work',
          disruption: {
            line_id: 'victoria',
            line_name: 'Victoria',
            mode: 'tube',
            status_severity: 6,
            status_severity_description: 'Minor Delays',
            reason: 'Signal failure',
            created_at: '2025-01-01T10:00:00Z',
            affected_routes: null,
          },
          affected_segments: [0, 1],
          affected_stations: ['940GZZLUOXC'],
        },
      ]

      vi.mocked(useUserRouteDisruptions).mockReturnValue({
        ...mockUseUserRouteDisruptions,
        disruptions: mockDisruptions,
      })

      renderWithRouter(<Routes />)

      // Should show disruption badge
      expect(screen.getByText('Minor Delays')).toBeInTheDocument()
      expect(screen.getByText('Victoria')).toBeInTheDocument()
    })

    it('should pass disruptions loading state to RouteList', () => {
      vi.mocked(useUserRouteDisruptions).mockReturnValue({
        ...mockUseUserRouteDisruptions,
        loading: true,
      })

      renderWithRouter(<Routes />)

      // Should show loading state
      const status = screen.getByRole('status', { name: /loading disruption status/i })
      expect(status).toBeInTheDocument()
    })

    it('should handle disruption errors gracefully', () => {
      const mockError = new ApiError(500, 'Failed to load disruptions')
      vi.mocked(useUserRouteDisruptions).mockReturnValue({
        ...mockUseUserRouteDisruptions,
        error: mockError,
      })

      renderWithRouter(<Routes />)

      // Should still render routes (graceful degradation)
      expect(screen.getByText('Home to Work')).toBeInTheDocument()
      // Should show good service as fallback
      expect(screen.getByText('Good Service')).toBeInTheDocument()
    })
  })
})
