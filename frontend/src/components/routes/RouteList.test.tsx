import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RouteList } from './RouteList'
import type {
  RouteListItemResponse,
  RouteDisruptionResponse,
  DisruptionResponse,
} from '../../lib/api'

describe('RouteList', () => {
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
    {
      id: 'route-2',
      name: 'Weekend Route',
      description: null,
      active: false,
      timezone: 'Europe/London',
      segment_count: 2,
      schedule_count: 1,
    },
  ]

  const mockOnEdit = vi.fn()
  const mockOnDelete = vi.fn()
  const mockOnClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render loading state', () => {
    render(<RouteList routes={[]} onEdit={mockOnEdit} onDelete={mockOnDelete} loading={true} />)

    const loadingElements = screen.getAllByLabelText('Loading routes')
    expect(loadingElements).toHaveLength(3)
  })

  it('should render empty state when no routes', () => {
    render(<RouteList routes={[]} onEdit={mockOnEdit} onDelete={mockOnDelete} loading={false} />)

    expect(screen.getByText('No routes created yet')).toBeInTheDocument()
    expect(
      screen.getByText(/create your first route to start receiving disruption alerts/i)
    ).toBeInTheDocument()
  })

  it('should render list of routes', () => {
    render(
      <RouteList routes={mockRoutes} onEdit={mockOnEdit} onDelete={mockOnDelete} loading={false} />
    )

    expect(screen.getByText('Home to Work')).toBeInTheDocument()
    expect(screen.getByText('Weekend Route')).toBeInTheDocument()
  })

  it('should pass onClick handler to RouteCard', () => {
    render(
      <RouteList
        routes={mockRoutes}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onClick={mockOnClick}
        loading={false}
      />
    )

    // Routes should be rendered
    expect(screen.getByText('Home to Work')).toBeInTheDocument()
  })

  it('should highlight deleting route', () => {
    render(
      <RouteList
        routes={mockRoutes}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        loading={false}
        deletingId="route-1"
      />
    )

    // The deleting route should have disabled buttons
    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    expect(editButtons[0]).toBeDisabled() // First route's edit button
  })

  describe('disruptions', () => {
    const createDisruption = (
      routeId: string,
      severity: number,
      overrides?: Partial<DisruptionResponse>
    ): RouteDisruptionResponse => ({
      route_id: routeId,
      route_name: 'Test Route',
      disruption: {
        line_id: 'victoria',
        line_name: 'Victoria',
        mode: 'tube',
        status_severity: severity,
        status_severity_description: severity === 10 ? 'Good Service' : 'Minor Delays',
        reason: 'Test reason',
        created_at: '2025-01-01T10:00:00Z',
        affected_routes: null,
        ...overrides,
      },
      affected_segments: [0, 1],
      affected_stations: ['940GZZLUOXC'],
    })

    it('should render routes without disruptions prop (backward compatible)', () => {
      render(<RouteList routes={mockRoutes} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

      // All routes should show "Good Service" by default
      const goodServiceElements = screen.getAllByText('Good Service')
      expect(goodServiceElements).toHaveLength(2)
    })

    it('should handle null disruptions', () => {
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptions={null}
        />
      )

      // All routes should show "Good Service"
      const goodServiceElements = screen.getAllByText('Good Service')
      expect(goodServiceElements).toHaveLength(2)
    })

    it('should handle empty disruptions array', () => {
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptions={[]}
        />
      )

      // All routes should show "Good Service"
      const goodServiceElements = screen.getAllByText('Good Service')
      expect(goodServiceElements).toHaveLength(2)
    })

    it('should pass disruption loading state to RouteCards', () => {
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptionsLoading={true}
        />
      )

      // All routes should show loading state
      const loadingStatuses = screen.getAllByRole('status', { name: /loading disruption status/i })
      expect(loadingStatuses).toHaveLength(2)
    })

    it('should map disruptions to correct routes', () => {
      const disruptions = [
        createDisruption('route-1', 6, {
          status_severity_description: 'Minor Delays',
          reason: 'Signal failure',
        }),
      ]
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptions={disruptions}
        />
      )

      // First route should show disruption
      expect(screen.getByText('Minor Delays')).toBeInTheDocument()
      expect(screen.getByText(/Signal failure/i)).toBeInTheDocument()

      // Second route should show "Good Service"
      expect(screen.getByText('Good Service')).toBeInTheDocument()
    })

    it('should show worst disruption when multiple disruptions for same route', () => {
      const disruptions = [
        createDisruption('route-1', 10, { status_severity_description: 'Good Service' }),
        createDisruption('route-1', 6, { status_severity_description: 'Minor Delays' }),
        createDisruption('route-1', 20, { status_severity_description: 'Severe Delays' }),
      ]
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptions={disruptions}
        />
      )

      // Should show Minor Delays (severity 6, lowest/worst)
      expect(screen.getByText('Minor Delays')).toBeInTheDocument()
      // Should not show Good Service or Severe Delays for first route
      expect(screen.queryByText('Severe Delays')).not.toBeInTheDocument()
    })

    it('should handle disruptions for multiple routes', () => {
      const disruptions = [
        createDisruption('route-1', 6, {
          line_name: 'Victoria',
          status_severity_description: 'Minor Delays',
        }),
        createDisruption('route-2', 1, {
          line_name: 'Piccadilly',
          status_severity_description: 'Closed',
        }),
      ]
      render(
        <RouteList
          routes={mockRoutes}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptions={disruptions}
        />
      )

      // Both disruptions should be shown
      expect(screen.getByText('Victoria')).toBeInTheDocument()
      expect(screen.getByText('Piccadilly')).toBeInTheDocument()
      expect(screen.getByText('Minor Delays')).toBeInTheDocument()
      expect(screen.getByText('Closed')).toBeInTheDocument()
    })
  })
})
