import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { ScheduleCard } from './ScheduleCard'

describe('ScheduleCard', () => {
  const defaultProps = {
    daysOfWeek: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
    startTime: '09:00:00',
    endTime: '17:00:00',
    onEdit: vi.fn(),
    onDelete: vi.fn(),
  }

  it('should render days of week as badges', () => {
    render(<ScheduleCard {...defaultProps} />)

    expect(screen.getByText('Mon')).toBeInTheDocument()
    expect(screen.getByText('Tue')).toBeInTheDocument()
    expect(screen.getByText('Wed')).toBeInTheDocument()
    expect(screen.getByText('Thu')).toBeInTheDocument()
    expect(screen.getByText('Fri')).toBeInTheDocument()
  })

  it('should format and display time range', () => {
    render(<ScheduleCard {...defaultProps} />)

    expect(screen.getByText('09:00 - 17:00')).toBeInTheDocument()
  })

  it('should call onEdit when edit button clicked', async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()

    render(<ScheduleCard {...defaultProps} onEdit={onEdit} />)

    await user.click(screen.getByLabelText('Edit schedule'))

    expect(onEdit).toHaveBeenCalledTimes(1)
  })

  it('should call onDelete when delete button clicked', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()

    render(<ScheduleCard {...defaultProps} onDelete={onDelete} />)

    await user.click(screen.getByLabelText('Delete schedule'))

    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('should disable buttons when isDeleting is true', () => {
    render(<ScheduleCard {...defaultProps} isDeleting={true} />)

    expect(screen.getByLabelText('Edit schedule')).toBeDisabled()
    expect(screen.getByLabelText('Delete schedule')).toBeDisabled()
  })

  it('should render weekend days', () => {
    render(<ScheduleCard {...defaultProps} daysOfWeek={['SAT', 'SUN']} />)

    expect(screen.getByText('Sat')).toBeInTheDocument()
    expect(screen.getByText('Sun')).toBeInTheDocument()
  })

  it('should handle different time formats', () => {
    render(<ScheduleCard {...defaultProps} startTime="06:30:00" endTime="22:45:00" />)

    expect(screen.getByText('06:30 - 22:45')).toBeInTheDocument()
  })
})
