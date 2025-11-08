import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import userEvent from '@testing-library/user-event'
import { SegmentBuilder } from './SegmentBuilder'
import type { SegmentResponse, LineResponse, StationResponse } from '../../lib/api'

describe('SegmentBuilder', () => {
  const mockLines: LineResponse[] = [
    {
      id: 'line-1',
      tfl_id: 'northern',
      name: 'Northern',
      color: '#000000',
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  const mockStations: StationResponse[] = [
    {
      id: 'station-1',
      tfl_id: '940GZZLUKSX',
      name: "King's Cross St. Pancras",
      latitude: 51.5308,
      longitude: -0.1238,
      lines: ['northern'],
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'station-2',
      tfl_id: '940GZZLUEUS',
      name: 'Euston',
      latitude: 51.5282,
      longitude: -0.1337,
      lines: ['northern'],
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  const mockInitialSegments: SegmentResponse[] = [
    {
      id: 'segment-1',
      sequence: 0,
      station_id: 'station-1',
      line_id: 'line-1',
    },
    {
      id: 'segment-2',
      sequence: 1,
      station_id: 'station-2',
      line_id: 'line-1',
    },
  ]

  const defaultProps = {
    routeId: 'route-1',
    initialSegments: mockInitialSegments,
    lines: mockLines,
    stations: mockStations,
    getLinesForStation: vi.fn(() => mockLines),
    onValidate: vi.fn(async () => ({ valid: true, message: 'Valid route' })),
    onSave: vi.fn(async () => {}),
    onCancel: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render initial segments', () => {
    render(<SegmentBuilder {...defaultProps} />)

    expect(screen.getByText("King's Cross St. Pancras")).toBeInTheDocument()
    expect(screen.getByText('Euston')).toBeInTheDocument()
  })

  it('should show instructions for adding stations', () => {
    render(<SegmentBuilder {...defaultProps} initialSegments={[]} />)

    expect(screen.getByText(/Select your starting station to begin your route/)).toBeInTheDocument()
  })

  it('should show route path heading', () => {
    render(<SegmentBuilder {...defaultProps} />)

    expect(screen.getByText('Route Path')).toBeInTheDocument()
  })

  it('should have cancel button when building route', () => {
    render(<SegmentBuilder {...defaultProps} initialSegments={[]} />)

    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
  })

  it('should not have save button (destination auto-saves)', () => {
    render(<SegmentBuilder {...defaultProps} />)

    expect(screen.queryByRole('button', { name: /Save Segments/i })).not.toBeInTheDocument()
  })

  it('should call onCancel when cancel button clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(<SegmentBuilder {...defaultProps} initialSegments={[]} onCancel={onCancel} />)

    const cancelButton = screen.getByRole('button', { name: /Cancel/i })
    await user.click(cancelButton)

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('should show cancel button during route building', async () => {
    const props = {
      ...defaultProps,
      initialSegments: [mockInitialSegments[0]],
    }

    render(<SegmentBuilder {...props} />)

    // Cancel button should be present during building
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
  })

  it('should show edit route button when route is complete', async () => {
    // Route with destination (line_id: null)
    const completeRoute: SegmentResponse[] = [
      mockInitialSegments[0],
      {
        id: 'segment-2',
        sequence: 1,
        station_id: 'station-2',
        line_id: null, // Destination
      },
    ]

    render(<SegmentBuilder {...defaultProps} initialSegments={completeRoute} />)

    // Edit Route button should be present
    expect(screen.getByRole('button', { name: /Edit Route/i })).toBeInTheDocument()
  })

  it('should hide continue journey card when route is complete', async () => {
    // Route with destination (line_id: null)
    const completeRoute: SegmentResponse[] = [
      mockInitialSegments[0],
      {
        id: 'segment-2',
        sequence: 1,
        station_id: 'station-2',
        line_id: null, // Destination
      },
    ]

    render(<SegmentBuilder {...defaultProps} initialSegments={completeRoute} />)

    // "Continue Your Journey" card should not be present
    expect(screen.queryByText('Continue Your Journey')).not.toBeInTheDocument()
  })

  it('should show add segment form', () => {
    render(<SegmentBuilder {...defaultProps} initialSegments={[]} />)

    expect(screen.getByText('Add Starting Station')).toBeInTheDocument()
    // Note: No "Add Segment" button in new button-based UI
    // Line buttons and destination button appear after station selection
  })
})
