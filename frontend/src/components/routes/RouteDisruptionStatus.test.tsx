import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { RouteDisruptionStatus } from './RouteDisruptionStatus'
import type { RouteDisruptionResponse, DisruptionResponse } from '@/types'

// Helper function to create mock disruption data
const createDisruption = (overrides?: Partial<DisruptionResponse>): RouteDisruptionResponse => ({
  route_id: 'route-1',
  route_name: 'Home to Work',
  disruption: {
    line_id: 'victoria',
    line_name: 'Victoria',
    mode: 'tube',
    status_severity: 6,
    status_severity_description: 'Minor Delays',
    reason: 'Victoria: Signal failure at Kings Cross',
    created_at: '2025-01-01T10:00:00Z',
    affected_routes: null,
    ...overrides,
  },
  affected_segments: [0, 1],
  affected_stations: ['940GZZLUOXC'],
})

describe('RouteDisruptionStatus', () => {
  describe('loading state', () => {
    it('should render loading skeleton when loading is true', () => {
      render(<RouteDisruptionStatus disruption={null} loading={true} />)

      const status = screen.getByRole('status')
      expect(status).toHaveAttribute('aria-busy', 'true')
      expect(status).toHaveAttribute('aria-label', 'Loading disruption status')

      // Check for skeleton element (animated placeholder)
      const skeleton = status.querySelector('.animate-pulse')
      expect(skeleton).toBeInTheDocument()
    })

    it('should render loading skeleton even when disruption is provided', () => {
      const disruption = createDisruption()
      render(<RouteDisruptionStatus disruption={disruption} loading={true} />)

      const status = screen.getByRole('status')
      expect(status).toHaveAttribute('aria-busy', 'true')

      // Should show loading, not the disruption
      expect(screen.queryByText('Victoria')).not.toBeInTheDocument()
    })
  })

  describe('good service state', () => {
    it('should render "Good Service" when disruption is null and not loading', () => {
      render(<RouteDisruptionStatus disruption={null} loading={false} />)

      const status = screen.getByRole('status')
      expect(status).toHaveAttribute('aria-label', 'Good Service')

      expect(screen.getByText('Good Service')).toBeInTheDocument()
    })

    it('should render CheckCircle icon for good service', () => {
      render(<RouteDisruptionStatus disruption={null} />)

      const icon = screen.getByRole('status').querySelector('svg')
      expect(icon).toBeInTheDocument()
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })
  })

  describe('disruption state', () => {
    it('should render disruption badge and line name', () => {
      const disruption = createDisruption()
      render(<RouteDisruptionStatus disruption={disruption} />)

      // Should show line name
      expect(screen.getByText('Victoria')).toBeInTheDocument()

      // Should show severity badge (DisruptionBadge has role="status")
      const badge = screen.getByRole('status', { name: 'Minor Delays' })
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveTextContent('Minor Delays')
    })

    it('should render disruption reason without line name prefix', () => {
      const disruption = createDisruption({
        reason: 'Victoria: Signal failure at Kings Cross',
      })
      render(<RouteDisruptionStatus disruption={disruption} />)

      // Should strip "Victoria: " prefix
      expect(screen.getByText(/Signal failure at Kings Cross/i)).toBeInTheDocument()
      expect(screen.queryByText(/Victoria: Signal failure/i)).not.toBeInTheDocument()
    })

    it('should render disruption reason as-is when no line name prefix', () => {
      const disruption = createDisruption({
        reason: 'Signal failure at Kings Cross',
      })
      render(<RouteDisruptionStatus disruption={disruption} />)

      expect(screen.getByText('Signal failure at Kings Cross')).toBeInTheDocument()
    })

    it('should not render reason text when reason is null', () => {
      const disruption = createDisruption({
        reason: null,
      })
      const { container } = render(<RouteDisruptionStatus disruption={disruption} />)

      // Should show line name and badge
      expect(screen.getByText('Victoria')).toBeInTheDocument()

      // Should not have a paragraph with reason
      const reason = container.querySelector('p')
      expect(reason).toBeNull()
    })

    it('should handle severe disruptions (low severity number)', () => {
      const disruption = createDisruption({
        status_severity: 1,
        status_severity_description: 'Closed',
        reason: 'Line closed due to emergency',
      })
      render(<RouteDisruptionStatus disruption={disruption} />)

      const badge = screen.getByRole('status', { name: 'Closed' })
      expect(badge).toHaveTextContent('Closed')
      expect(screen.getByText('Victoria')).toBeInTheDocument()
      expect(screen.getByText(/emergency/i)).toBeInTheDocument()
    })

    it('should handle good service severity (severity 10)', () => {
      const disruption = createDisruption({
        status_severity: 10,
        status_severity_description: 'Good Service',
        reason: null,
      })
      render(<RouteDisruptionStatus disruption={disruption} />)

      const badge = screen.getByRole('status', { name: 'Good Service' })
      expect(badge).toHaveTextContent('Good Service')
    })

    it('should clamp long reason text to 2 lines', () => {
      const longReason = 'A'.repeat(200)
      const disruption = createDisruption({
        reason: longReason,
      })
      render(<RouteDisruptionStatus disruption={disruption} />)

      const reasonElement = screen.getByTitle(longReason)
      expect(reasonElement).toHaveClass('line-clamp-2')
    })
  })

  describe('custom styling', () => {
    it('should accept and apply custom className', () => {
      render(<RouteDisruptionStatus disruption={null} className="custom-class" />)

      const status = screen.getByRole('status')
      expect(status).toHaveClass('custom-class')
    })

    it('should apply custom className to loading state', () => {
      render(<RouteDisruptionStatus disruption={null} loading={true} className="custom-class" />)

      const status = screen.getByRole('status')
      expect(status).toHaveClass('custom-class')
    })

    it('should apply custom className to disruption state', () => {
      const disruption = createDisruption()
      const { container } = render(
        <RouteDisruptionStatus disruption={disruption} className="custom-class" />
      )

      // The outer div should have the custom class
      const outerDiv = container.firstChild as HTMLElement
      expect(outerDiv).toHaveClass('custom-class')
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA labels for all states', () => {
      const { rerender } = render(<RouteDisruptionStatus disruption={null} loading={true} />)
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading disruption status')

      rerender(<RouteDisruptionStatus disruption={null} loading={false} />)
      expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Good Service')

      const disruption = createDisruption()
      rerender(<RouteDisruptionStatus disruption={disruption} loading={false} />)
      // DisruptionBadge has role="status" with appropriate aria-label
      const badge = screen.getByRole('status')
      expect(badge).toHaveAttribute('aria-label', 'Minor Delays')
    })

    it('should mark decorative icons as aria-hidden', () => {
      render(<RouteDisruptionStatus disruption={null} />)

      const icon = screen.getByRole('status').querySelector('svg')
      expect(icon).toHaveAttribute('aria-hidden', 'true')
    })

    it('should use role="status" for live region updates', () => {
      // Loading state has role="status"
      const { rerender } = render(<RouteDisruptionStatus disruption={null} loading={true} />)
      expect(screen.getByRole('status')).toBeInTheDocument()

      // Good service state has role="status"
      rerender(<RouteDisruptionStatus disruption={null} loading={false} />)
      expect(screen.getByRole('status')).toBeInTheDocument()

      // Disruption state has role="status" on the badge
      const disruption = createDisruption()
      rerender(<RouteDisruptionStatus disruption={disruption} />)
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
  })
})
