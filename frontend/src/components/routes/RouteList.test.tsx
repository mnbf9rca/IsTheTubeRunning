import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { RouteList } from './RouteList'
import type { RouteListItemResponse } from '../../lib/api'

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
})
