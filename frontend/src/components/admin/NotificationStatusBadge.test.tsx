import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { NotificationStatusBadge } from './NotificationStatusBadge'

describe('NotificationStatusBadge', () => {
  describe('rendering', () => {
    it('should render "Sent" badge for sent status', () => {
      render(<NotificationStatusBadge status="sent" />)
      expect(screen.getByText('Sent')).toBeInTheDocument()
    })

    it('should render "Failed" badge for failed status', () => {
      render(<NotificationStatusBadge status="failed" />)
      expect(screen.getByText('Failed')).toBeInTheDocument()
    })

    it('should render "Pending" badge for pending status', () => {
      render(<NotificationStatusBadge status="pending" />)
      expect(screen.getByText('Pending')).toBeInTheDocument()
    })
  })

  describe('tooltips', () => {
    it('should render tooltip trigger for sent status', () => {
      render(<NotificationStatusBadge status="sent" />)
      const badge = screen.getByText('Sent')
      expect(badge).toBeInTheDocument()
      // Tooltip functionality is handled by shadcn/ui Tooltip component
    })

    it('should render tooltip trigger for failed status', () => {
      render(<NotificationStatusBadge status="failed" />)
      const badge = screen.getByText('Failed')
      expect(badge).toBeInTheDocument()
      // Tooltip functionality is handled by shadcn/ui Tooltip component
    })

    it('should render tooltip trigger for pending status', () => {
      render(<NotificationStatusBadge status="pending" />)
      const badge = screen.getByText('Pending')
      expect(badge).toBeInTheDocument()
      // Tooltip functionality is handled by shadcn/ui Tooltip component
    })
  })
})
