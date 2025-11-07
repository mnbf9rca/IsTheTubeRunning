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

  it('should have save and cancel buttons', () => {
    render(<SegmentBuilder {...defaultProps} />)

    expect(screen.getByRole('button', { name: /Save Segments/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
  })

  it('should disable save button when no changes', () => {
    render(<SegmentBuilder {...defaultProps} />)

    const saveButton = screen.getByRole('button', { name: /Save Segments/i })
    expect(saveButton).toBeDisabled()
  })

  it('should call onCancel when cancel button clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(<SegmentBuilder {...defaultProps} onCancel={onCancel} />)

    const cancelButton = screen.getByRole('button', { name: /Cancel/i })
    await user.click(cancelButton)

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('should disable save button when less than 2 segments', async () => {
    const user = userEvent.setup()
    const props = {
      ...defaultProps,
      initialSegments: [mockInitialSegments[0]],
    }

    render(<SegmentBuilder {...props} />)

    // Delete the only segment first
    const deleteButton = screen.getByLabelText(/Delete segment/)
    await user.click(deleteButton)

    // Save button should be disabled (less than 2 segments)
    const saveButton = screen.getByRole('button', { name: /Save Segments/i })
    expect(saveButton).toBeDisabled()
  })

  it('should enable save button when there are changes and at least 2 segments', async () => {
    const user = userEvent.setup()
    const onValidate = vi.fn(async () => ({ valid: true, message: 'Valid route' }))
    const onSave = vi.fn(async () => {})

    // Start with 3 segments so we can delete one and still have 2
    const threeSegments: SegmentResponse[] = [
      ...mockInitialSegments,
      {
        id: 'segment-3',
        sequence: 2,
        station_id: 'station-2',
        line_id: 'line-1',
      },
    ]

    render(
      <SegmentBuilder
        {...defaultProps}
        initialSegments={threeSegments}
        onValidate={onValidate}
        onSave={onSave}
      />
    )

    // Delete a segment to create changes (3 -> 2 segments, still valid)
    const deleteButtons = screen.getAllByLabelText(/Delete segment/)
    await user.click(deleteButtons[2])

    // Save button should be enabled (has changes AND >= 2 segments)
    const saveButton = screen.getByRole('button', { name: /Save Segments/i })
    expect(saveButton).not.toBeDisabled()
  })

  it('should disable save button when only 1 segment remains after deletion', async () => {
    const user = userEvent.setup()
    const onValidate = vi.fn(async () => ({
      valid: false,
      message: 'Invalid connection between stations',
      invalid_segment_index: 1,
    }))

    render(<SegmentBuilder {...defaultProps} onValidate={onValidate} />)

    // Delete a segment to make changes (2 segments -> 1 segment)
    const deleteButtons = screen.getAllByLabelText(/Delete segment/)
    await user.click(deleteButtons[1])

    // Save button should be disabled (only 1 segment remaining)
    const saveButton = screen.getByRole('button', { name: /Save Segments/i })
    expect(saveButton).toBeDisabled()
  })

  it('should show add segment form', () => {
    render(<SegmentBuilder {...defaultProps} initialSegments={[]} />)

    expect(screen.getByText('Add Starting Station')).toBeInTheDocument()
    // Note: No "Add Segment" button in new button-based UI
    // Line buttons and destination button appear after station selection
  })
})
