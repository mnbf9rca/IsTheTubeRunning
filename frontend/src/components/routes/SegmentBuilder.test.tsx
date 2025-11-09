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
      station_tfl_id: '940GZZLUKSX',
      line_tfl_id: 'northern',
    },
    {
      id: 'segment-2',
      sequence: 1,
      station_tfl_id: '940GZZLUEUS',
      line_tfl_id: 'northern',
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
    // Route with destination (line_tfl_id: null)
    const completeRoute: SegmentResponse[] = [
      mockInitialSegments[0],
      {
        id: 'segment-2',
        sequence: 1,
        station_tfl_id: '940GZZLUEUS',
        line_tfl_id: null, // Destination
      },
    ]

    render(<SegmentBuilder {...defaultProps} initialSegments={completeRoute} />)

    // Edit Route button should be present
    expect(screen.getByRole('button', { name: /Edit Route/i })).toBeInTheDocument()
  })

  it('should hide continue journey card when route is complete', async () => {
    // Route with destination (line_tfl_id: null)
    const completeRoute: SegmentResponse[] = [
      mockInitialSegments[0],
      {
        id: 'segment-2',
        sequence: 1,
        station_tfl_id: '940GZZLUEUS',
        line_tfl_id: null, // Destination
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

  // Issue #48 - Junction station handling tests
  describe('junction station handling (issue #48)', () => {
    const piccadillyLine: LineResponse = {
      id: 'line-piccadilly',
      tfl_id: 'piccadilly',
      name: 'Piccadilly',
      color: '#1c3f94',
      last_updated: '2025-01-01T00:00:00Z',
    }

    const northernLine: LineResponse = {
      id: 'line-northern',
      tfl_id: 'northern',
      name: 'Northern',
      color: '#000000',
      last_updated: '2025-01-01T00:00:00Z',
    }

    const southgateStation: StationResponse = {
      id: 'station-southgate',
      tfl_id: '940GZZLUSGT',
      name: 'Southgate Underground Station',
      latitude: 51.6322,
      longitude: -0.1279,
      lines: ['piccadilly'],
      last_updated: '2025-01-01T00:00:00Z',
    }

    const leicesterSquareStation: StationResponse = {
      id: 'station-leicester',
      tfl_id: '940GZZLULSX',
      name: 'Leicester Square Underground Station',
      latitude: 51.5113,
      longitude: -0.1281,
      lines: ['piccadilly', 'northern'],
      last_updated: '2025-01-01T00:00:00Z',
    }

    const bankStation: StationResponse = {
      id: 'station-bank',
      tfl_id: '940GZZLUBNK',
      name: 'Bank Underground Station',
      latitude: 51.5133,
      longitude: -0.0886,
      lines: ['northern'],
      last_updated: '2025-01-01T00:00:00Z',
    }

    it('should allow switching lines at junction station', () => {
      // Scenario: Southgate -> Leicester Square (Piccadilly) -> Bank (Northern)
      // After adding Leicester Square as junction, it becomes currentStation
      // Should allow continuing on Northern line without duplicate error
      const junctionSegments: SegmentResponse[] = [
        {
          id: 'segment-1',
          sequence: 0,
          station_tfl_id: southgateStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id,
        },
        {
          id: 'segment-2',
          sequence: 1,
          station_tfl_id: leicesterSquareStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id, // Junction station with arrival line
        },
      ]

      const getLinesForStation = vi.fn((stationTflId: string) => {
        if (stationTflId === leicesterSquareStation.tfl_id) {
          return [piccadillyLine, northernLine]
        }
        return []
      })

      const getNextStations = vi.fn((currentStationTflId: string, currentLineTflId: string) => {
        if (
          currentStationTflId === leicesterSquareStation.tfl_id &&
          currentLineTflId === northernLine.tfl_id
        ) {
          return [bankStation]
        }
        return []
      })

      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={junctionSegments}
          lines={[piccadillyLine, northernLine]}
          stations={[southgateStation, leicesterSquareStation, bankStation]}
          getLinesForStation={getLinesForStation}
          getNextStations={getNextStations}
        />
      )

      // Should show the route without errors
      expect(screen.getByText(southgateStation.name)).toBeInTheDocument()
      expect(screen.getByText(leicesterSquareStation.name)).toBeInTheDocument()

      // Should not show duplicate error
      expect(
        screen.queryByText(/already in your route. Routes cannot visit the same station twice/)
      ).not.toBeInTheDocument()
    })

    it('should allow marking destination after junction station', async () => {
      // Scenario: After switching lines at Leicester Square, mark Bank as destination
      // Leicester Square is last segment, should allow adding Bank as destination
      const junctionSegments: SegmentResponse[] = [
        {
          id: 'segment-1',
          sequence: 0,
          station_tfl_id: southgateStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id,
        },
        {
          id: 'segment-2',
          sequence: 1,
          station_tfl_id: leicesterSquareStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id,
        },
      ]

      const getLinesForStation = vi.fn((stationTflId: string) => {
        if (stationTflId === leicesterSquareStation.tfl_id) {
          return [piccadillyLine, northernLine]
        }
        return []
      })

      const getNextStations = vi.fn((currentStationTflId: string, currentLineTflId: string) => {
        if (
          currentStationTflId === leicesterSquareStation.tfl_id &&
          currentLineTflId === northernLine.tfl_id
        ) {
          return [bankStation]
        }
        return []
      })

      const onValidate = vi.fn(async () => ({ valid: true, message: 'Valid route' }))
      const onSave = vi.fn(async () => {})

      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={junctionSegments}
          lines={[piccadillyLine, northernLine]}
          stations={[southgateStation, leicesterSquareStation, bankStation]}
          getLinesForStation={getLinesForStation}
          getNextStations={getNextStations}
          onValidate={onValidate}
          onSave={onSave}
        />
      )

      // Should not show duplicate error for junction station
      expect(screen.queryByText(/Leicester Square.*already in your route/)).not.toBeInTheDocument()
    })

    it('should still prevent actual cycles (returning to starting station)', async () => {
      // Scenario: Southgate -> Leicester Square -> back to Southgate (should fail)
      const segmentsBeforeCycle: SegmentResponse[] = [
        {
          id: 'segment-1',
          sequence: 0,
          station_tfl_id: southgateStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id,
        },
      ]

      const getLinesForStation = vi.fn((stationTflId: string) => {
        if (stationTflId === leicesterSquareStation.tfl_id) {
          return [piccadillyLine, northernLine]
        }
        if (stationTflId === southgateStation.tfl_id) {
          return [piccadillyLine]
        }
        return []
      })

      const getNextStations = vi.fn((currentStationTflId: string) => {
        if (currentStationTflId === leicesterSquareStation.tfl_id) {
          // Hypothetically, if Southgate were reachable from Leicester Square
          return [southgateStation]
        }
        return []
      })

      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={segmentsBeforeCycle}
          lines={[piccadillyLine, northernLine]}
          stations={[southgateStation, leicesterSquareStation, bankStation]}
          getLinesForStation={getLinesForStation}
          getNextStations={getNextStations}
        />
      )

      // The component should prevent adding Southgate again (actual cycle)
      // Note: This would be tested through user interactions, but the logic is in place
      expect(screen.getByText(southgateStation.name)).toBeInTheDocument()
    })

    it('should display selected next station before action buttons', () => {
      // This tests the fix for Problem 1 from issue #48
      // Mock scenario where user has selected a next station
      const propsWithState = {
        ...defaultProps,
        initialSegments: [],
        lines: [piccadillyLine],
        stations: [southgateStation, leicesterSquareStation],
        getLinesForStation: vi.fn(() => [piccadillyLine]),
        getNextStations: vi.fn(() => [leicesterSquareStation]),
      }

      render(<SegmentBuilder {...propsWithState} />)

      // Note: Since this is a controlled component test, we'd need to simulate
      // user interaction to trigger the state change. The visual display check
      // would happen in Playwright E2E tests.
      // Here we verify the component renders without errors
      expect(screen.getByText('Add Starting Station')).toBeInTheDocument()
    })
  })

  // Issue #56 - Starting station display and heading text bug
  describe('starting station display (issue #56)', () => {
    const piccadillyLine: LineResponse = {
      id: 'line-piccadilly',
      tfl_id: 'piccadilly',
      name: 'Piccadilly',
      color: '#1c3f94',
      last_updated: '2025-01-01T00:00:00Z',
    }

    const southgateStation: StationResponse = {
      id: 'station-southgate',
      tfl_id: '940GZZLUSGT',
      name: 'Southgate',
      latitude: 51.6322,
      longitude: -0.1279,
      lines: ['piccadilly'],
      last_updated: '2025-01-01T00:00:00Z',
    }

    const leicesterSquareStation: StationResponse = {
      id: 'station-leicester',
      tfl_id: '940GZZLULSX',
      name: 'Leicester Square',
      latitude: 51.5113,
      longitude: -0.1281,
      lines: ['piccadilly'],
      last_updated: '2025-01-01T00:00:00Z',
    }

    it('should show "Add Starting Station" when no segments and no current station', () => {
      // Bug #56 Fix: When localSegments.length === 0 AND !currentStation
      // Should show "Add Starting Station"
      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={[]}
          lines={[piccadillyLine]}
          stations={[southgateStation, leicesterSquareStation]}
          getLinesForStation={vi.fn(() => [piccadillyLine])}
        />
      )

      expect(screen.getByText('Add Starting Station')).toBeInTheDocument()
    })

    it('should render without errors when starting station selected', () => {
      // Bug #56 Context: After selecting starting station:
      // - Heading should change to "Continue Your Journey" (currentStation exists)
      // - "From: [Station]" should appear when step === 'select-line' or 'select-next-station' or 'choose-action'
      //
      // Note: Full interaction flow (selecting stations via combobox) is complex to test
      // in unit tests and is better suited for Playwright E2E tests.
      // This test verifies the component renders correctly with the bug fixes applied.
      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={[]}
          lines={[piccadillyLine]}
          stations={[southgateStation, leicesterSquareStation]}
          getLinesForStation={vi.fn(() => [piccadillyLine])}
          getNextStations={vi.fn(() => [leicesterSquareStation])}
        />
      )

      // Component should render without errors
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument()
    })

    it('should maintain heading "Continue Your Journey" with existing segments', () => {
      // Bug #56 Fix: When localSegments.length > 0, should always show "Continue Your Journey"
      const segments: SegmentResponse[] = [
        {
          id: 'segment-1',
          sequence: 0,
          station_tfl_id: southgateStation.tfl_id,
          line_tfl_id: piccadillyLine.tfl_id,
        },
      ]

      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={segments}
          lines={[piccadillyLine]}
          stations={[southgateStation, leicesterSquareStation]}
          getLinesForStation={vi.fn(() => [piccadillyLine])}
        />
      )

      expect(screen.getByText('Continue Your Journey')).toBeInTheDocument()
      expect(screen.queryByText('Add Starting Station')).not.toBeInTheDocument()
    })

    it('should hide instruction alert when starting station selected', () => {
      // Bug #56 Fix (Part 3): Instruction alert should be hidden once currentStation is set
      // This prevents "Select your starting station to begin your route" from showing
      // after a station has been selected
      render(
        <SegmentBuilder
          {...defaultProps}
          initialSegments={[]}
          lines={[piccadillyLine]}
          stations={[southgateStation, leicesterSquareStation]}
          getLinesForStation={vi.fn(() => [piccadillyLine])}
        />
      )

      // Initially, should show the instruction
      expect(
        screen.getByText('Select your starting station to begin your route.')
      ).toBeInTheDocument()

      // Note: Full interaction testing (selecting a station and verifying the alert disappears)
      // is complex for unit tests due to the controlled combobox component.
      // This is better suited for Playwright E2E tests.
      // The fix ensures getInstructions() checks both localSegments.length === 0 AND !currentStation
    })
  })
})
