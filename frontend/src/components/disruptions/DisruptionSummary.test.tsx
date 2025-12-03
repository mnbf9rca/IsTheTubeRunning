import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DisruptionSummary } from './DisruptionSummary'
import type { DisruptionResponse } from '@/types'

describe('DisruptionSummary', () => {
  const createDisruption = (lineId: string, mode: string): DisruptionResponse => ({
    line_id: lineId,
    line_name: lineId.charAt(0).toUpperCase() + lineId.slice(1),
    mode,
    status_severity: 10,
    status_severity_description: 'Minor Delays',
    reason: 'Test disruption',
    created_at: '2025-01-01T10:00:00Z',
    affected_routes: null,
  })

  describe('empty disruptions', () => {
    it('should show good service message when no disruptions', () => {
      render(<DisruptionSummary disruptions={[]} />)

      expect(screen.getByText('Good service on all lines')).toBeInTheDocument()
    })

    it('should have role="status" for accessibility', () => {
      render(<DisruptionSummary disruptions={[]} />)

      const summary = screen.getByRole('status')
      expect(summary).toBeInTheDocument()
    })
  })

  describe('with some disruptions', () => {
    it('should show good service message for other lines', () => {
      const disruptions = [createDisruption('piccadilly', 'tube')]

      render(<DisruptionSummary disruptions={disruptions} />)

      expect(screen.getByText('Good service on all other lines')).toBeInTheDocument()
    })

    it('should show message with multiple disruptions on different modes', () => {
      const disruptions = [createDisruption('piccadilly', 'tube'), createDisruption('dlr', 'dlr')]

      render(<DisruptionSummary disruptions={disruptions} />)

      expect(screen.getByText('Good service on all other lines')).toBeInTheDocument()
    })
  })

  describe('custom className', () => {
    it('should apply custom className', () => {
      const { container } = render(<DisruptionSummary disruptions={[]} className="custom-class" />)

      expect(container.firstChild).toHaveClass('custom-class')
    })

    it('should preserve default classes with custom className', () => {
      const { container } = render(<DisruptionSummary disruptions={[]} className="custom-class" />)

      expect(container.firstChild).toHaveClass('text-sm')
      expect(container.firstChild).toHaveClass('text-muted-foreground')
      expect(container.firstChild).toHaveClass('custom-class')
    })
  })
})
