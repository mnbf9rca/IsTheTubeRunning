import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { LineSelect } from './LineSelect'
import type { LineResponse } from '../../lib/api'

describe('LineSelect', () => {
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
    {
      id: 'line-3',
      tfl_id: 'circle',
      name: 'Circle',
      color: '#FFD300',
      last_updated: '2025-01-01T00:00:00Z',
    },
  ]

  it('should render placeholder when no line selected', () => {
    const onChange = vi.fn()
    render(
      <LineSelect
        lines={mockLines}
        value={undefined}
        onChange={onChange}
        placeholder="Choose a line"
      />
    )

    expect(screen.getByText('Choose a line')).toBeInTheDocument()
  })

  it('should display selected line', () => {
    const onChange = vi.fn()
    render(<LineSelect lines={mockLines} value="line-2" onChange={onChange} />)

    // The trigger should show the selected line name
    expect(screen.getByRole('combobox')).toHaveTextContent('Victoria')
  })

  it('should call onChange when line is selected', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<LineSelect lines={mockLines} value={undefined} onChange={onChange} />)

    // Click trigger to open dropdown
    const trigger = screen.getByRole('combobox')
    await user.click(trigger)

    // Select a line (note: radix-ui Select uses different DOM structure)
    const northernOption = screen.getByRole('option', { name: /Northern/i })
    await user.click(northernOption)

    expect(onChange).toHaveBeenCalledWith('line-1')
  })

  it('should be disabled when disabled prop is true', () => {
    const onChange = vi.fn()
    render(<LineSelect lines={mockLines} value={undefined} onChange={onChange} disabled />)

    const trigger = screen.getByRole('combobox')
    expect(trigger).toBeDisabled()
  })

  it('should render all lines in dropdown', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(<LineSelect lines={mockLines} value={undefined} onChange={onChange} />)

    // Open dropdown
    await user.click(screen.getByRole('combobox'))

    // All lines should be present
    expect(screen.getByRole('option', { name: /Northern/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Victoria/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Circle/i })).toBeInTheDocument()
  })

  it('should have accessible aria-label', () => {
    const onChange = vi.fn()
    render(
      <LineSelect
        lines={mockLines}
        value={undefined}
        onChange={onChange}
        aria-label="Pick tube line"
      />
    )

    expect(screen.getByLabelText('Pick tube line')).toBeInTheDocument()
  })
})
