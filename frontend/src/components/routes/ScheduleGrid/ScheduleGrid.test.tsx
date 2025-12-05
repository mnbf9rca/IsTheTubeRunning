import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ScheduleGrid } from './ScheduleGrid'

describe('ScheduleGrid', () => {
  describe('rendering', () => {
    it('should render day headers', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      expect(screen.getByText('Mon')).toBeInTheDocument()
      expect(screen.getByText('Tue')).toBeInTheDocument()
      expect(screen.getByText('Wed')).toBeInTheDocument()
      expect(screen.getByText('Thu')).toBeInTheDocument()
      expect(screen.getByText('Fri')).toBeInTheDocument()
      expect(screen.getByText('Sat')).toBeInTheDocument()
      expect(screen.getByText('Sun')).toBeInTheDocument()
    })

    it('should render time labels for hours', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      // Should show hour markers (just hour numbers, not minutes)
      expect(screen.getByText('00')).toBeInTheDocument()
      expect(screen.getByText('01')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('23')).toBeInTheDocument()
    })

    it('should render grid cells', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      // Should have cells for each day-slot combination
      // 7 days × 96 slots = 672 cells
      const cells = screen.getAllByRole('button')
      expect(cells.length).toBe(672)
    })

    it('should show selected cells', () => {
      const onChange = vi.fn()
      const initialSelection = new Set(['MON:0', 'TUE:5'])

      render(<ScheduleGrid initialSelection={initialSelection} onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')
      expect(monCell).toHaveAttribute('aria-pressed', 'true')
      expect(monCell).toHaveClass('bg-primary')
    })

    it('should show unselected cells', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')
      expect(monCell).toHaveAttribute('aria-pressed', 'false')
      expect(monCell).toHaveClass('bg-background')
    })
  })

  describe('interaction', () => {
    it('should toggle cell on click', async () => {
      const user = userEvent.setup()
      const onChange = vi.fn()

      render(<ScheduleGrid onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')

      await user.click(monCell)

      expect(onChange).toHaveBeenCalledTimes(1)
      const selection = onChange.mock.calls[0][0]
      expect(selection.has('MON:0')).toBe(true)
    })

    it('should deselect cell on second click', async () => {
      const user = userEvent.setup()
      const onChange = vi.fn()
      const initialSelection = new Set(['MON:0'])

      render(<ScheduleGrid initialSelection={initialSelection} onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')

      await user.click(monCell)

      expect(onChange).toHaveBeenCalledTimes(1)
      const selection = onChange.mock.calls[0][0]
      expect(selection.has('MON:0')).toBe(false)
    })

    it('should not respond to clicks when disabled', async () => {
      const user = userEvent.setup()
      const onChange = vi.fn()

      render(<ScheduleGrid onChange={onChange} disabled={true} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')

      await user.click(monCell)

      expect(onChange).not.toHaveBeenCalled()
    })

    it('should disable all cells when disabled prop is true', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} disabled={true} />)

      const cells = screen.getAllByRole('button')
      cells.forEach((cell) => {
        expect(cell).toBeDisabled()
      })
    })
  })

  describe('accessibility', () => {
    it('should have aria-labels for cells', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')
      expect(monCell).toBeInTheDocument()

      const tueCell = screen.getByLabelText('Tue 09:00:00')
      expect(tueCell).toBeInTheDocument()
    })

    it('should have aria-pressed for selected state', () => {
      const onChange = vi.fn()
      const initialSelection = new Set(['MON:0'])

      render(<ScheduleGrid initialSelection={initialSelection} onChange={onChange} />)

      const monCell = screen.getByLabelText('Mon 00:00:00')
      expect(monCell).toHaveAttribute('aria-pressed', 'true')

      const tueCell = screen.getByLabelText('Tue 00:00:00')
      expect(tueCell).toHaveAttribute('aria-pressed', 'false')
    })

    it('should have button role for cells', () => {
      const onChange = vi.fn()
      render(<ScheduleGrid onChange={onChange} />)

      const cells = screen.getAllByRole('button')
      expect(cells.length).toBeGreaterThan(0)
    })
  })

  describe('className prop', () => {
    it('should apply custom className to container', () => {
      const onChange = vi.fn()
      const { container } = render(<ScheduleGrid onChange={onChange} className="custom-class" />)

      const card = container.querySelector('.custom-class')
      expect(card).toBeInTheDocument()
    })
  })

  describe('initialSelection updates', () => {
    it('should update selection when initialSelection prop changes', () => {
      const onChange = vi.fn()
      const { rerender } = render(
        <ScheduleGrid initialSelection={new Set(['MON:0'])} onChange={onChange} />
      )

      let monCell = screen.getByLabelText('Mon 00:00:00')
      expect(monCell).toHaveAttribute('aria-pressed', 'true')

      rerender(<ScheduleGrid initialSelection={new Set(['TUE:5'])} onChange={onChange} />)

      monCell = screen.getByLabelText('Mon 00:00:00')
      const tueCell = screen.getByLabelText('Tue 01:15:00')

      expect(monCell).toHaveAttribute('aria-pressed', 'false')
      expect(tueCell).toHaveAttribute('aria-pressed', 'true')
    })
  })
})
