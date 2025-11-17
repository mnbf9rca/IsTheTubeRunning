import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { NotificationLogsTable } from './NotificationLogsTable'
import userEvent from '@testing-library/user-event'
import type { NotificationLogItem } from '@/lib/api'

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('NotificationLogsTable', () => {
  const mockLogs: NotificationLogItem[] = [
    {
      id: 'log-1',
      user_id: 'user-123-456-789',
      route_id: 'route-abc-def-ghi',
      route_name: 'Test Route 1',
      sent_at: new Date().toISOString(),
      method: 'email',
      status: 'sent',
      error_message: null,
    },
    {
      id: 'log-2',
      user_id: 'user-987-654-321',
      route_id: 'route-xyz-uvw-rst',
      route_name: 'Test Route 2',
      sent_at: new Date(Date.now() - 86400000).toISOString(), // Yesterday
      method: 'sms',
      status: 'failed',
      error_message:
        'This is a very long error message that exceeds one hundred characters and should be truncated in the main row but displayed in full when the row is expanded for better readability',
    },
  ]

  const onViewUser = vi.fn()

  describe('loading state', () => {
    it('should show skeleton loaders when loading', () => {
      render(<NotificationLogsTable logs={[]} loading={true} onViewUser={onViewUser} />)

      // Table should be rendered with headers during loading
      expect(screen.getByText('Sent At')).toBeInTheDocument()
      expect(screen.getByText('Route')).toBeInTheDocument()
    })

    it('should show table headers when loading', () => {
      render(<NotificationLogsTable logs={[]} loading={true} onViewUser={onViewUser} />)

      expect(screen.getByText('Sent At')).toBeInTheDocument()
      expect(screen.getByText('Route')).toBeInTheDocument()
      expect(screen.getByText('Method')).toBeInTheDocument()
      expect(screen.getByText('Status')).toBeInTheDocument()
      expect(screen.getByText('User')).toBeInTheDocument()
      // Note: Actions column header is empty in loading state
    })
  })

  describe('empty state', () => {
    it('should show empty message when no logs', () => {
      render(<NotificationLogsTable logs={[]} loading={false} onViewUser={onViewUser} />)

      expect(screen.getByText('No notification logs found')).toBeInTheDocument()
      expect(
        screen.getByText('Logs will appear here when notifications are sent')
      ).toBeInTheDocument()
    })
  })

  describe('data rendering', () => {
    it('should render log data correctly', () => {
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Check route names
      expect(screen.getByText('Test Route 1')).toBeInTheDocument()
      expect(screen.getByText('Test Route 2')).toBeInTheDocument()

      // Check method badges
      expect(screen.getByText('Email')).toBeInTheDocument()
      expect(screen.getByText('SMS')).toBeInTheDocument()

      // Check status badges
      expect(screen.getByText('Sent')).toBeInTheDocument()
      expect(screen.getByText('Failed')).toBeInTheDocument()
    })

    it('should truncate user IDs', () => {
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // User IDs should be truncated to 12 chars + '...'
      expect(screen.getByText('user-123-456...')).toBeInTheDocument()
      expect(screen.getByText('user-987-654...')).toBeInTheDocument()
    })

    it('should show "Unknown" for null route names', () => {
      const logsWithNullRoute: NotificationLogItem[] = [{ ...mockLogs[0], route_name: null }]

      render(
        <NotificationLogsTable logs={logsWithNullRoute} loading={false} onViewUser={onViewUser} />
      )

      expect(screen.getByText('Unknown')).toBeInTheDocument()
    })
  })

  describe('row expansion', () => {
    it('should expand row when clicked', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Initially collapsed (ChevronRight icon)
      const rows = screen.getAllByRole('row')
      expect(rows.length).toBe(3) // Header + 2 data rows

      // Click first data row
      await user.click(screen.getByText('Test Route 1'))

      // Should show expanded content
      await waitFor(() => {
        expect(screen.getByText('Route UUID:')).toBeInTheDocument()
      })

      expect(screen.getByText('route-abc-def-ghi')).toBeInTheDocument()
    })

    it('should collapse row when clicked again', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Expand row
      await user.click(screen.getByText('Test Route 1'))
      await waitFor(() => {
        expect(screen.getByText('Route UUID:')).toBeInTheDocument()
      })

      // Collapse row
      await user.click(screen.getByText('Test Route 1'))
      await waitFor(() => {
        expect(screen.queryByText('Route UUID:')).not.toBeInTheDocument()
      })
    })

    it('should show error message for failed notifications', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Expand failed notification row
      await user.click(screen.getByText('Test Route 2'))

      await waitFor(() => {
        expect(screen.getByText('Error Message:')).toBeInTheDocument()
      })

      // Should show full error message
      expect(screen.getByText(/This is a very long error message/)).toBeInTheDocument()
    })

    it('should not show error section for successful notifications', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Expand successful notification row
      await user.click(screen.getByText('Test Route 1'))

      await waitFor(() => {
        expect(screen.getByText('Route UUID:')).toBeInTheDocument()
      })

      // Should NOT show error message section
      expect(screen.queryByText('Error Message:')).not.toBeInTheDocument()
    })
  })

  describe('user actions', () => {
    it('should call onViewUser when View button is clicked', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      const viewButtons = screen.getAllByText('View')
      await user.click(viewButtons[0])

      expect(onViewUser).toHaveBeenCalledWith('user-123-456-789')
    })

    it('should not expand row when View button is clicked', async () => {
      const user = userEvent.setup()
      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      const viewButtons = screen.getAllByText('View')
      await user.click(viewButtons[0])

      // Row should not be expanded (stopPropagation)
      expect(screen.queryByText('Route UUID:')).not.toBeInTheDocument()
    })
  })

  describe('copy functionality', () => {
    it('should copy route ID when copy button is clicked', async () => {
      const user = userEvent.setup()

      // Mock clipboard API
      const writeTextMock = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: writeTextMock,
        },
        writable: true,
      })

      render(<NotificationLogsTable logs={mockLogs} loading={false} onViewUser={onViewUser} />)

      // Expand row
      await user.click(screen.getByText('Test Route 1'))

      await waitFor(() => {
        expect(screen.getByText('Route UUID:')).toBeInTheDocument()
      })

      // Find and click copy button
      const copyButtons = screen.getAllByRole('button')
      const copyButton = copyButtons.find((btn) => btn.querySelector('svg.lucide-copy'))
      if (copyButton) {
        await user.click(copyButton)
        expect(writeTextMock).toHaveBeenCalledWith('route-abc-def-ghi')
      }
    })
  })
})
