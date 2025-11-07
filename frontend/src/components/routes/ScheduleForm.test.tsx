import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { ScheduleForm } from './ScheduleForm'

describe('ScheduleForm', () => {
  const defaultProps = {
    onSave: vi.fn(async () => {}),
    onCancel: vi.fn(),
  }

  it('should render form with day toggles and time inputs', () => {
    render(<ScheduleForm {...defaultProps} />)

    expect(screen.getByLabelText('Days of Week')).toBeInTheDocument()
    expect(screen.getByLabelText('Start Time')).toBeInTheDocument()
    expect(screen.getByLabelText('End Time')).toBeInTheDocument()
  })

  it('should render all day buttons', () => {
    render(<ScheduleForm {...defaultProps} />)

    expect(screen.getByLabelText('Toggle Mon')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Tue')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Wed')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Thu')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Fri')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Sat')).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Sun')).toBeInTheDocument()
  })

  it('should call onCancel when cancel button clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(<ScheduleForm {...defaultProps} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: /Cancel/i }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('should show error when no days selected', async () => {
    const user = userEvent.setup()
    render(<ScheduleForm {...defaultProps} />)

    // Try to submit without selecting days
    await user.click(screen.getByRole('button', { name: /Create/i }))

    expect(await screen.findByText('Please select at least one day')).toBeInTheDocument()
  })

  it('should populate initial values when editing', () => {
    render(
      <ScheduleForm
        {...defaultProps}
        initialDays={['MON', 'FRI']}
        initialStartTime="08:00"
        initialEndTime="18:00"
        isEditing={true}
      />
    )

    expect(screen.getByText('Edit Schedule')).toBeInTheDocument()
    const monButton = screen.getByLabelText('Toggle Mon')
    expect(monButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('should toggle day selection', async () => {
    const user = userEvent.setup()
    render(<ScheduleForm {...defaultProps} />)

    const monButton = screen.getByLabelText('Toggle Mon')

    // Initially not selected
    expect(monButton).toHaveAttribute('aria-pressed', 'false')

    // Click to select
    await user.click(monButton)
    expect(monButton).toHaveAttribute('aria-pressed', 'true')

    // Click to deselect
    await user.click(monButton)
    expect(monButton).toHaveAttribute('aria-pressed', 'false')
  })
})
