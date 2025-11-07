import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { SegmentList } from './SegmentList'
import type { SegmentResponse, LineResponse, StationResponse } from '../../lib/api'

describe('SegmentList', () => {
  const mockLines: LineResponse[] = [
    {
      id: 'line-1',
      tfl_id: 'northern',
      name: 'Northern',
      color: '#000000',
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'line-2',
      tfl_id: 'victoria',
      name: 'Victoria',
      color: '#0098D8',
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
      lines: ['northern', 'victoria'],
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
    {
      id: 'station-3',
      tfl_id: '940GZZLUEMB',
      name: 'Embankment',
      latitude: 51.5074,
      longitude: -0.1224,
      lines: ['northern'],
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  const mockSegments: SegmentResponse[] = [
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
    {
      id: 'segment-3',
      sequence: 2,
      station_id: 'station-3',
      line_id: 'line-1',
    },
  ]

  it('should show empty state when no segments', () => {
    render(
      <SegmentList
        segments={[]}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    expect(screen.getByText('No segments yet')).toBeInTheDocument()
    expect(
      screen.getByText('Add your first station to start building your route.')
    ).toBeInTheDocument()
  })

  it('should render all segments in order', () => {
    render(
      <SegmentList
        segments={mockSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    expect(screen.getByText("King's Cross St. Pancras")).toBeInTheDocument()
    expect(screen.getByText('Euston')).toBeInTheDocument()
    expect(screen.getByText('Embankment')).toBeInTheDocument()
  })

  it('should render segments with line information', () => {
    render(
      <SegmentList
        segments={mockSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    // All segments are on Northern line
    const lineLabels = screen.getAllByText('Northern line')
    expect(lineLabels).toHaveLength(3)
  })

  it('should call onDeleteSegment with correct sequence', async () => {
    const user = userEvent.setup()
    const onDeleteSegment = vi.fn()

    render(
      <SegmentList
        segments={mockSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={onDeleteSegment}
      />
    )

    // Click delete on second segment (Euston)
    const deleteButtons = screen.getAllByLabelText(/Delete segment/)
    await user.click(deleteButtons[1])

    expect(onDeleteSegment).toHaveBeenCalledWith(1)
  })

  it('should allow deletion when more than 2 segments', () => {
    render(
      <SegmentList
        segments={mockSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    const deleteButtons = screen.getAllByLabelText(/Delete segment/)
    deleteButtons.forEach((button) => {
      expect(button).not.toBeDisabled()
    })
  })

  it('should disable deletion when only 2 segments', () => {
    const twoSegments = mockSegments.slice(0, 2)

    render(
      <SegmentList
        segments={twoSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    const deleteButtons = screen.getAllByLabelText(/Delete segment/)
    deleteButtons.forEach((button) => {
      expect(button).toBeDisabled()
    })
  })

  it('should sort segments by sequence number', () => {
    // Provide segments in wrong order
    const unsortedSegments = [mockSegments[2], mockSegments[0], mockSegments[1]]

    render(
      <SegmentList
        segments={unsortedSegments}
        lines={mockLines}
        stations={mockStations}
        onDeleteSegment={vi.fn()}
      />
    )

    // Check they appear in correct order by checking sequence numbers
    const sequenceNumbers = screen.getAllByText(/^[1-3]$/)
    expect(sequenceNumbers[0]).toHaveTextContent('1')
    expect(sequenceNumbers[1]).toHaveTextContent('2')
    expect(sequenceNumbers[2]).toHaveTextContent('3')
  })
})
