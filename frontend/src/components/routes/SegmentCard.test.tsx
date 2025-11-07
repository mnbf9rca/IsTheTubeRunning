import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { SegmentCard } from './SegmentCard'

describe('SegmentCard', () => {
  const defaultProps = {
    stationName: "King's Cross St. Pancras",
    lineName: 'Northern',
    lineColor: '#000000',
    sequence: 0,
    isLast: false,
    canDelete: true,
    onDelete: vi.fn(),
  }

  it('should render station name and line information', () => {
    render(<SegmentCard {...defaultProps} />)

    expect(screen.getByText("King's Cross St. Pancras")).toBeInTheDocument()
    expect(screen.getByText('Northern line')).toBeInTheDocument()
  })

  it('should display sequence number (1-indexed)', () => {
    render(<SegmentCard {...defaultProps} sequence={2} />)

    // Sequence 2 should display as "3"
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('should show arrow when not last segment', () => {
    const { container } = render(<SegmentCard {...defaultProps} isLast={false} />)

    // Arrow icon should be present (ArrowRight has lucide-arrow-right class)
    const arrow = container.querySelector('.lucide-arrow-right')
    expect(arrow).toBeInTheDocument()
  })

  it('should not show arrow when last segment', () => {
    const { container } = render(<SegmentCard {...defaultProps} isLast={true} />)

    // Arrow icon should not be present (ArrowRight has lucide-arrow-right class)
    const arrow = container.querySelector('.lucide-arrow-right')
    expect(arrow).not.toBeInTheDocument()
  })

  it('should call onDelete when delete button clicked', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()

    render(<SegmentCard {...defaultProps} onDelete={onDelete} />)

    const deleteButton = screen.getByLabelText('Delete segment 1')
    await user.click(deleteButton)

    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('should disable delete button when canDelete is false', () => {
    render(<SegmentCard {...defaultProps} canDelete={false} />)

    const deleteButton = screen.getByLabelText('Delete segment 1')
    expect(deleteButton).toBeDisabled()
  })

  it('should enable delete button when canDelete is true', () => {
    render(<SegmentCard {...defaultProps} canDelete={true} />)

    const deleteButton = screen.getByLabelText('Delete segment 1')
    expect(deleteButton).not.toBeDisabled()
  })
})
