import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LineButton } from './LineButton'
import type { LineResponse } from '@/types'
import { CORPORATE_BLUE, WHITE } from '@/lib/tfl-colors'

describe('LineButton', () => {
  const mockPiccadillyLine: LineResponse = {
    id: '1',
    tfl_id: 'piccadilly',
    name: 'Piccadilly',
    mode: 'tube',
    last_updated: '2024-01-01T00:00:00Z',
  }

  const mockCircleLine: LineResponse = {
    id: '2',
    tfl_id: 'circle',
    name: 'Circle',
    mode: 'tube',
    last_updated: '2024-01-01T00:00:00Z',
  }

  it('renders line name correctly', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} />)

    expect(screen.getByText('Piccadilly')).toBeInTheDocument()
  })

  it('uses white text for most lines (e.g., Piccadilly)', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveStyle({ color: WHITE })
  })

  it('uses Corporate Blue text for Circle line', () => {
    render(<LineButton line={mockCircleLine} onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Travel on Circle line/i,
    })
    expect(button).toHaveStyle({ color: CORPORATE_BLUE })
  })

  it('applies correct background color', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    // Piccadilly line should have official TfL Piccadilly blue background
    expect(button).toHaveStyle({ backgroundColor: '#003688' })
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const handleClick = vi.fn()

    render(<LineButton line={mockPiccadillyLine} onClick={handleClick} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    await user.click(button)

    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('shows selected state with aria-pressed', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} selected={true} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveAttribute('aria-pressed', 'true')
  })

  it('shows unselected state with aria-pressed false', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} selected={false} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveAttribute('aria-pressed', 'false')
  })

  it('applies correct size class for sm', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} size="sm" />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveClass('h-8')
  })

  it('applies correct size class for md (default)', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveClass('h-10')
  })

  it('applies correct size class for lg', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} size="lg" />)

    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    expect(button).toHaveClass('h-12')
  })

  it('includes train icon', () => {
    render(<LineButton line={mockPiccadillyLine} onClick={vi.fn()} />)

    // Train icon should be present (lucide-react Train component)
    const button = screen.getByRole('button', {
      name: /Travel on Piccadilly line/i,
    })
    const icon = button.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })
})
