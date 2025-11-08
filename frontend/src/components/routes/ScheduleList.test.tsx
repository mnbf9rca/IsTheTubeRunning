import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { ScheduleList } from './ScheduleList'
import type { ScheduleResponse } from '../../lib/api'

describe('ScheduleList', () => {
  const mockSchedules: ScheduleResponse[] = [
    {
      id: 'schedule-1',
      days_of_week: ['MON', 'TUE', 'WED', 'THU', 'FRI'],
      start_time: '09:00:00',
      end_time: '17:00:00',
    },
    {
      id: 'schedule-2',
      days_of_week: ['SAT', 'SUN'],
      start_time: '10:00:00',
      end_time: '14:00:00',
    },
  ]

  it('should show empty state when no schedules', () => {
    render(<ScheduleList schedules={[]} onEdit={vi.fn()} onDelete={vi.fn()} />)

    expect(screen.getByText('No schedules configured')).toBeInTheDocument()
    expect(
      screen.getByText(/Add a schedule to specify when this route should be monitored/)
    ).toBeInTheDocument()
  })

  it('should render all schedules', () => {
    render(<ScheduleList schedules={mockSchedules} onEdit={vi.fn()} onDelete={vi.fn()} />)

    // Check weekday schedule
    expect(screen.getByText('Mon')).toBeInTheDocument()
    expect(screen.getByText('09:00 - 17:00')).toBeInTheDocument()

    // Check weekend schedule
    expect(screen.getByText('Sat')).toBeInTheDocument()
    expect(screen.getByText('10:00 - 14:00')).toBeInTheDocument()
  })

  it('should call onEdit with schedule ID', async () => {
    const user = userEvent.setup()
    const onEdit = vi.fn()

    render(<ScheduleList schedules={mockSchedules} onEdit={onEdit} onDelete={vi.fn()} />)

    const editButtons = screen.getAllByLabelText('Edit schedule')
    await user.click(editButtons[0])

    expect(onEdit).toHaveBeenCalledWith('schedule-1')
  })

  it('should call onDelete with schedule ID', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()

    render(<ScheduleList schedules={mockSchedules} onEdit={vi.fn()} onDelete={onDelete} />)

    const deleteButtons = screen.getAllByLabelText('Delete schedule')
    await user.click(deleteButtons[1])

    expect(onDelete).toHaveBeenCalledWith('schedule-2')
  })

  it('should show loading state on schedule being deleted', () => {
    render(
      <ScheduleList
        schedules={mockSchedules}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        deletingScheduleId="schedule-1"
      />
    )

    const editButtons = screen.getAllByLabelText('Edit schedule')
    expect(editButtons[0]).toBeDisabled()
    expect(editButtons[1]).not.toBeDisabled()
  })
})
