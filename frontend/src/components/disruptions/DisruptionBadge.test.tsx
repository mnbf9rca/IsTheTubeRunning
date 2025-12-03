import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { DisruptionBadge } from './DisruptionBadge'

describe('DisruptionBadge', () => {
  describe('severity mapping', () => {
    it('should render good service with secondary variant', () => {
      render(<DisruptionBadge severity={10} severityDescription="Good Service" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Good Service')
      expect(badge).toHaveAttribute('aria-label', 'Good Service')
    })

    it('should render minor delays with outline variant', () => {
      render(<DisruptionBadge severity={6} severityDescription="Minor Delays" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Minor Delays')
      expect(badge).toHaveAttribute('aria-label', 'Minor Delays')
    })

    it('should render severe disruption with destructive variant', () => {
      render(<DisruptionBadge severity={20} severityDescription="Severe Delays" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Severe Delays')
      expect(badge).toHaveAttribute('aria-label', 'Severe Delays')
    })

    it('should handle low severity numbers (1-4) as destructive', () => {
      render(<DisruptionBadge severity={3} severityDescription="Part Closure" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Part Closure')
    })

    it('should handle high severity numbers (11-20) as destructive', () => {
      render(<DisruptionBadge severity={15} severityDescription="Suspended" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Suspended')
    })
  })

  describe('compact mode', () => {
    it('should render compact mode with dot', () => {
      render(<DisruptionBadge severity={10} compact />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('•')
      expect(badge).toHaveAttribute('aria-label', 'Good Service')
    })

    it('should use severity description in aria-label for compact mode', () => {
      render(<DisruptionBadge severity={6} severityDescription="Minor Delays" compact />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('•')
      expect(badge).toHaveAttribute('aria-label', 'Minor Delays')
    })
  })

  describe('aria labels', () => {
    it('should use severityDescription for aria-label when provided', () => {
      render(<DisruptionBadge severity={10} severityDescription="Custom Description" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveAttribute('aria-label', 'Custom Description')
    })

    it('should fallback to default label when no description provided', () => {
      render(<DisruptionBadge severity={10} />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveAttribute('aria-label', 'Good Service')
    })

    it('should use "Minor Delays" label for severity 5-9', () => {
      render(<DisruptionBadge severity={7} />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveAttribute('aria-label', 'Minor Delays')
    })

    it('should use "Severe Disruption" label for severity <5 or >10', () => {
      render(<DisruptionBadge severity={2} />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveAttribute('aria-label', 'Severe Disruption')
    })
  })

  describe('custom className', () => {
    it('should apply custom className', () => {
      render(<DisruptionBadge severity={10} className="custom-class" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveClass('custom-class')
    })
  })

  describe('full mode', () => {
    it('should display severity description in full mode', () => {
      render(<DisruptionBadge severity={10} severityDescription="All Good" />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('All Good')
      expect(badge).not.toHaveTextContent('•')
    })

    it('should display fallback label when no description provided', () => {
      render(<DisruptionBadge severity={10} />)

      const badge = screen.getByRole('status')
      expect(badge).toHaveTextContent('Good Service')
    })
  })
})
