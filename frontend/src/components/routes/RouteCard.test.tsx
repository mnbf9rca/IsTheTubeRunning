import { render, screen } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { RouteCard } from './RouteCard'
import type {
  RouteListItemResponse,
  RouteDisruptionResponse,
  DisruptionResponse,
} from '../../lib/api'

describe('RouteCard', () => {
  const mockRoute: RouteListItemResponse = {
    id: 'route-1',
    name: 'Home to Work',
    description: 'Daily commute via Victoria line',
    active: true,
    timezone: 'Europe/London',
    segment_count: 3,
    schedule_count: 2,
  }

  const mockOnEdit = vi.fn()
  const mockOnDelete = vi.fn()
  const mockOnClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render route information', () => {
    render(<RouteCard route={mockRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

    expect(screen.getByText('Home to Work')).toBeInTheDocument()
    expect(screen.getByText('Daily commute via Victoria line')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('3 segments')).toBeInTheDocument()
    expect(screen.getByText('2 schedules')).toBeInTheDocument()
  })

  it('should render inactive badge for inactive routes', () => {
    const inactiveRoute = { ...mockRoute, active: false }
    render(<RouteCard route={inactiveRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

    expect(screen.getByText('Inactive')).toBeInTheDocument()
  })

  it('should not render description if null', () => {
    const routeWithoutDesc = { ...mockRoute, description: null }
    render(<RouteCard route={routeWithoutDesc} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

    expect(screen.queryByText('Daily commute via Victoria line')).not.toBeInTheDocument()
  })

  it('should call onEdit when edit button clicked', async () => {
    const user = userEvent.setup()
    render(<RouteCard route={mockRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

    const editButton = screen.getByRole('button', { name: /edit route home to work/i })
    await user.click(editButton)

    expect(mockOnEdit).toHaveBeenCalledWith('route-1')
    expect(mockOnEdit).toHaveBeenCalledTimes(1)
  })

  it('should call onDelete when delete button clicked', async () => {
    const user = userEvent.setup()
    render(<RouteCard route={mockRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

    const deleteButton = screen.getByRole('button', { name: /delete route home to work/i })
    await user.click(deleteButton)

    expect(mockOnDelete).toHaveBeenCalledWith('route-1')
    expect(mockOnDelete).toHaveBeenCalledTimes(1)
  })

  it('should call onClick when card is clicked', async () => {
    const user = userEvent.setup()
    render(
      <RouteCard
        route={mockRoute}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onClick={mockOnClick}
      />
    )

    // Click on the card (not on buttons)
    const cardTitle = screen.getByText('Home to Work')
    await user.click(cardTitle)

    expect(mockOnClick).toHaveBeenCalledWith('route-1')
  })

  it('should not call onClick when buttons are clicked', async () => {
    const user = userEvent.setup()
    render(
      <RouteCard
        route={mockRoute}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        onClick={mockOnClick}
      />
    )

    const editButton = screen.getByRole('button', { name: /edit/i })
    await user.click(editButton)

    // onClick should not be called, only onEdit
    expect(mockOnClick).not.toHaveBeenCalled()
    expect(mockOnEdit).toHaveBeenCalled()
  })

  it('should disable buttons when isDeleting is true', () => {
    render(
      <RouteCard route={mockRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} isDeleting={true} />
    )

    const editButton = screen.getByRole('button', { name: /edit/i })
    const deleteButton = screen.getByRole('button', { name: /delete/i })

    expect(editButton).toBeDisabled()
    expect(deleteButton).toBeDisabled()
  })

  describe('disruption status', () => {
    const createDisruption = (
      overrides?: Partial<DisruptionResponse>
    ): RouteDisruptionResponse => ({
      route_id: 'route-1',
      route_name: 'Home to Work',
      disruption: {
        line_id: 'victoria',
        line_name: 'Victoria',
        mode: 'tube',
        status_severity: 6,
        status_severity_description: 'Minor Delays',
        reason: 'Signal failure at Kings Cross',
        created_at: '2025-01-01T10:00:00Z',
        affected_routes: null,
        ...overrides,
      },
      affected_segments: [0, 1],
      affected_stations: ['940GZZLUOXC'],
    })

    it('should render without disruption prop (backward compatible)', () => {
      render(<RouteCard route={mockRoute} onEdit={mockOnEdit} onDelete={mockOnDelete} />)

      // Should show "Good Service" by default when no disruption prop
      expect(screen.getByText('Good Service')).toBeInTheDocument()
    })

    it('should render disruption loading state', () => {
      render(
        <RouteCard
          route={mockRoute}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruptionsLoading={true}
        />
      )

      const status = screen.getByRole('status', { name: /loading disruption status/i })
      expect(status).toBeInTheDocument()
      expect(status).toHaveAttribute('aria-busy', 'true')
    })

    it('should render "Good Service" when disruption is null', () => {
      render(
        <RouteCard
          route={mockRoute}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruption={null}
          disruptionsLoading={false}
        />
      )

      expect(screen.getByText('Good Service')).toBeInTheDocument()
      expect(screen.getByRole('status', { name: 'Good Service' })).toBeInTheDocument()
    })

    it('should render disruption badge and details when disruption exists', () => {
      const disruption = createDisruption()
      render(
        <RouteCard
          route={mockRoute}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruption={disruption}
          disruptionsLoading={false}
        />
      )

      // Should show line name
      expect(screen.getByText('Victoria')).toBeInTheDocument()

      // Should show severity badge
      const badge = screen.getByRole('status', { name: 'Minor Delays' })
      expect(badge).toHaveTextContent('Minor Delays')

      // Should show reason
      expect(screen.getByText(/Signal failure at Kings Cross/i)).toBeInTheDocument()
    })

    it('should render severe disruption', () => {
      const disruption = createDisruption({
        status_severity: 1,
        status_severity_description: 'Closed',
        reason: 'Line closed',
      })
      render(
        <RouteCard
          route={mockRoute}
          onEdit={mockOnEdit}
          onDelete={mockOnDelete}
          disruption={disruption}
        />
      )

      expect(screen.getByText('Victoria')).toBeInTheDocument()
      const badge = screen.getByRole('status', { name: 'Closed' })
      expect(badge).toHaveTextContent('Closed')
    })
  })
})
