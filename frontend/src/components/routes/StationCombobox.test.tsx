import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { StationCombobox } from './StationCombobox'
import type { StationResponse } from '../../lib/api'

describe('StationCombobox', () => {
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
      lines: ['northern', 'victoria'],
      last_updated: '2025-01-01T00:00:00Z',
    },
    {
      id: 'station-3',
      tfl_id: '940GZZLUEMB',
      name: 'Embankment',
      latitude: 51.5074,
      longitude: -0.1224,
      lines: ['northern', 'circle'],
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  it('should render placeholder when no station selected', () => {
    const onChange = vi.fn()
    render(
      <StationCombobox
        stations={mockStations}
        value={undefined}
        onChange={onChange}
        placeholder="Choose a station"
      />
    )

    expect(screen.getByRole('combobox')).toHaveTextContent('Choose a station')
  })

  it('should display selected station name', () => {
    const onChange = vi.fn()
    render(<StationCombobox stations={mockStations} value="station-1" onChange={onChange} />)

    expect(screen.getByRole('combobox')).toHaveTextContent("King's Cross St. Pancras")
  })

  it('should open popover when button clicked', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Click combobox to open
    await user.click(screen.getByRole('combobox'))

    // Search input should appear
    expect(screen.getByPlaceholderText('Search stations...')).toBeInTheDocument()
  })

  it('should call onChange when station is selected', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Open combobox
    await user.click(screen.getByRole('combobox'))

    // Click a station
    const eustonOption = screen.getByText('Euston')
    await user.click(eustonOption)

    expect(onChange).toHaveBeenCalledWith('station-2')
  })

  it('should filter stations when searching', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Open combobox
    await user.click(screen.getByRole('combobox'))

    // Type in search
    const searchInput = screen.getByPlaceholderText('Search stations...')
    await user.type(searchInput, 'embankment')

    // Only Embankment should be visible
    expect(screen.getByText('Embankment')).toBeInTheDocument()
    expect(screen.queryByText('Euston')).not.toBeInTheDocument()
    expect(screen.queryByText("King's Cross St. Pancras")).not.toBeInTheDocument()
  })

  it('should show "No station found" when search has no results', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Open combobox
    await user.click(screen.getByRole('combobox'))

    // Search for non-existent station
    const searchInput = screen.getByPlaceholderText('Search stations...')
    await user.type(searchInput, 'nonexistent')

    expect(screen.getByText('No station found.')).toBeInTheDocument()
  })

  it('should be disabled when disabled prop is true', () => {
    const onChange = vi.fn()
    render(
      <StationCombobox stations={mockStations} value={undefined} onChange={onChange} disabled />
    )

    const button = screen.getByRole('combobox')
    expect(button).toBeDisabled()
  })

  it('should close popover after selection', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Open combobox
    await user.click(screen.getByRole('combobox'))
    expect(screen.getByPlaceholderText('Search stations...')).toBeInTheDocument()

    // Select a station
    await user.click(screen.getByText('Euston'))

    // Popover should close (search input should not be visible)
    expect(screen.queryByPlaceholderText('Search stations...')).not.toBeInTheDocument()
  })

  it('should have accessible aria-label', () => {
    const onChange = vi.fn()
    render(
      <StationCombobox
        stations={mockStations}
        value={undefined}
        onChange={onChange}
        aria-label="Pick tube station"
      />
    )

    expect(screen.getByLabelText('Pick tube station')).toBeInTheDocument()
  })

  it('should render all stations in list', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<StationCombobox stations={mockStations} value={undefined} onChange={onChange} />)

    // Open combobox
    await user.click(screen.getByRole('combobox'))

    // All stations should be present
    expect(screen.getByText("King's Cross St. Pancras")).toBeInTheDocument()
    expect(screen.getByText('Euston')).toBeInTheDocument()
    expect(screen.getByText('Embankment')).toBeInTheDocument()
  })
})
