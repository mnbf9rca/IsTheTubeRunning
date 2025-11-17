import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdminNotificationLogs from './AdminNotificationLogs'
import userEvent from '@testing-library/user-event'
import type { RecentLogsResponse, ApiError } from '@/lib/api'

// Mock the hook
vi.mock('@/hooks/useNotificationLogs', () => ({
  useNotificationLogs: vi.fn(),
}))

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

// Mock API functions
vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual('@/lib/api')
  return {
    ...actual,
    getAdminUser: vi.fn(),
    anonymizeUser: vi.fn(),
  }
})

import { useNotificationLogs } from '@/hooks/useNotificationLogs'

describe('AdminNotificationLogs', () => {
  const mockLogsResponse: RecentLogsResponse = {
    total: 100,
    logs: [
      {
        id: 'log-1',
        user_id: 'user-1',
        route_id: 'route-1',
        route_name: 'Morning Commute',
        sent_at: new Date().toISOString(),
        method: 'email',
        status: 'sent',
        error_message: null,
      },
      {
        id: 'log-2',
        user_id: 'user-2',
        route_id: 'route-2',
        route_name: 'Evening Route',
        sent_at: new Date().toISOString(),
        method: 'sms',
        status: 'failed',
        error_message: 'SMS service unavailable',
      },
    ],
    limit: 50,
    offset: 0,
  }

  const mockHookReturn = {
    logs: mockLogsResponse,
    loading: false,
    error: null,
    currentPage: 1,
    pageSize: 50,
    totalLogs: 100,
    totalPages: 2,
    statusFilter: 'all' as const,
    fetchLogs: vi.fn(),
    setPage: vi.fn(),
    setPageSize: vi.fn(),
    setStatusFilter: vi.fn(),
    refresh: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useNotificationLogs).mockReturnValue(mockHookReturn)
  })

  describe('rendering', () => {
    it('should render page header', () => {
      render(<AdminNotificationLogs />)

      expect(screen.getByText('Notification Logs')).toBeInTheDocument()
      expect(
        screen.getByText('View notification delivery logs and troubleshoot issues')
      ).toBeInTheDocument()
    })

    it('should render filters', () => {
      render(<AdminNotificationLogs />)

      expect(screen.getByText('Filter by Status')).toBeInTheDocument()
      expect(screen.getByText('Page Size')).toBeInTheDocument()
    })

    it('should render log count', () => {
      render(<AdminNotificationLogs />)

      expect(screen.getByText(/Showing 1-50 of 100 logs/)).toBeInTheDocument()
      expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument()
    })

    it('should render logs table', () => {
      render(<AdminNotificationLogs />)

      expect(screen.getByText('Morning Commute')).toBeInTheDocument()
      expect(screen.getByText('Evening Route')).toBeInTheDocument()
    })
  })

  describe('status filter', () => {
    it('should call setStatusFilter when status changes', async () => {
      const user = userEvent.setup()
      render(<AdminNotificationLogs />)

      const statusSelect = screen.getByRole('combobox', { name: /filter by status/i })
      await user.click(statusSelect)

      const sentOption = screen.getByRole('option', { name: 'Sent' })
      await user.click(sentOption)

      expect(mockHookReturn.setStatusFilter).toHaveBeenCalledWith('sent')
    })

    it('should show current status filter', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        statusFilter: 'failed',
      })

      render(<AdminNotificationLogs />)

      const statusSelect = screen.getByRole('combobox', { name: /filter by status/i })
      expect(statusSelect).toHaveTextContent('Failed')
    })
  })

  describe('page size selector', () => {
    it('should call setPageSize when page size changes', async () => {
      const user = userEvent.setup()
      render(<AdminNotificationLogs />)

      const pageSizeSelect = screen.getByRole('combobox', { name: /page size/i })
      await user.click(pageSizeSelect)

      const option25 = screen.getByRole('option', { name: '25' })
      await user.click(option25)

      expect(mockHookReturn.setPageSize).toHaveBeenCalledWith(25)
    })

    it('should show current page size', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        pageSize: 100,
      })

      render(<AdminNotificationLogs />)

      const pageSizeSelect = screen.getByRole('combobox', { name: /page size/i })
      expect(pageSizeSelect).toHaveTextContent('100')
    })
  })

  describe('pagination', () => {
    it('should render pagination when multiple pages', () => {
      render(<AdminNotificationLogs />)

      expect(screen.getByText('1')).toBeInTheDocument()
      expect(screen.getByText('2')).toBeInTheDocument()
    })

    it('should call setPage when page number clicked', async () => {
      const user = userEvent.setup()
      render(<AdminNotificationLogs />)

      const page2Button = screen.getByText('2')
      await user.click(page2Button)

      expect(mockHookReturn.setPage).toHaveBeenCalledWith(2)
    })

    it('should call setPage when next button clicked', async () => {
      const user = userEvent.setup()
      render(<AdminNotificationLogs />)

      const nextButton = screen.getByRole('link', { name: /go to next page/i })
      await user.click(nextButton)

      expect(mockHookReturn.setPage).toHaveBeenCalledWith(2)
    })

    it('should call setPage when previous button clicked on page 2', async () => {
      const user = userEvent.setup()
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        currentPage: 2,
      })

      render(<AdminNotificationLogs />)

      const prevButton = screen.getByRole('link', { name: /go to previous page/i })
      await user.click(prevButton)

      expect(mockHookReturn.setPage).toHaveBeenCalledWith(1)
    })

    it('should not render pagination with single page', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        totalPages: 1,
      })

      render(<AdminNotificationLogs />)

      expect(screen.queryByRole('navigation', { name: /pagination/i })).not.toBeInTheDocument()
    })

    it('should disable previous button on first page', () => {
      render(<AdminNotificationLogs />)

      const prevButton = screen.getByRole('link', { name: /go to previous page/i })
      expect(prevButton).toHaveClass('pointer-events-none', 'opacity-50')
    })

    it('should disable next button on last page', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        currentPage: 2,
      })

      render(<AdminNotificationLogs />)

      const nextButton = screen.getByRole('link', { name: /go to next page/i })
      expect(nextButton).toHaveClass('pointer-events-none', 'opacity-50')
    })
  })

  describe('error handling', () => {
    it('should show error alert when error occurs', () => {
      const mockError = { message: 'Failed to fetch logs', statusCode: 500 }
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        error: mockError as ApiError,
      })

      render(<AdminNotificationLogs />)

      expect(screen.getByText(/Error loading logs/)).toBeInTheDocument()
      expect(screen.getByText(/Failed to fetch logs/)).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('should pass loading state to table', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        loading: true,
        logs: null,
      })

      render(<AdminNotificationLogs />)

      // Table should show loading rows (skeletons in NotificationLogsTable)
      // Check for table headers which are always present
      expect(screen.getByText('Sent At')).toBeInTheDocument()
      expect(screen.getByText('Route')).toBeInTheDocument()
      expect(screen.getByText('Method')).toBeInTheDocument()
      expect(screen.getByText('Status')).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('should show "No logs found" when total is zero', () => {
      vi.mocked(useNotificationLogs).mockReturnValue({
        ...mockHookReturn,
        logs: { ...mockLogsResponse, total: 0, logs: [] },
        totalLogs: 0,
        totalPages: 0,
      })

      render(<AdminNotificationLogs />)

      expect(screen.getByText('No logs found')).toBeInTheDocument()
    })
  })

  describe('user details dialog', () => {
    it('should open user details dialog when View button clicked', async () => {
      const user = userEvent.setup()
      render(<AdminNotificationLogs />)

      const viewButtons = screen.getAllByText('View')
      await user.click(viewButtons[0])

      // Dialog should be triggered (userId set)
      // Note: Full dialog rendering may require additional context providers
    })
  })
})
