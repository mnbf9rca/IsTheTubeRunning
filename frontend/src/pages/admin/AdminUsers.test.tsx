import { render, screen, waitFor, within } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AdminUsers from './AdminUsers'
import { ApiError, type PaginatedUsersResponse, type UserDetailResponse } from '@/lib/api'

// Mock the useAdminUsers hook
vi.mock('@/hooks/useAdminUsers', () => ({
  useAdminUsers: vi.fn(),
}))

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { useAdminUsers } from '@/hooks/useAdminUsers'
import { toast } from 'sonner'

describe('AdminUsers', () => {
  const mockPaginatedResponse: PaginatedUsersResponse = {
    total: 25,
    users: [
      {
        id: 'user-1',
        external_id: 'auth0|123',
        auth_provider: 'auth0',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
        deleted_at: null,
        email_addresses: [
          { id: 'email-1', email: 'user1@example.com', verified: true, is_primary: true },
        ],
        phone_numbers: [],
      },
      {
        id: 'user-2',
        external_id: 'auth0|456',
        auth_provider: 'auth0',
        created_at: '2025-01-02T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        deleted_at: '2025-01-10T00:00:00Z',
        email_addresses: [],
        phone_numbers: [
          { id: 'phone-1', phone: '+442012345678', verified: false, is_primary: false },
        ],
      },
    ],
    limit: 50,
    offset: 0,
  }

  const mockUserDetail: UserDetailResponse = {
    id: 'user-1',
    external_id: 'auth0|123',
    auth_provider: 'auth0',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    deleted_at: null,
    email_addresses: [
      { id: 'email-1', email: 'user1@example.com', verified: true, is_primary: true },
    ],
    phone_numbers: [],
  }

  const mockSetPage = vi.fn()
  const mockSetSearchQuery = vi.fn()
  const mockSetIncludeDeleted = vi.fn()
  const mockGetUserDetails = vi.fn()
  const mockAnonymizeUser = vi.fn()

  const defaultMockHook = {
    users: mockPaginatedResponse,
    loading: false,
    error: null,
    currentPage: 1,
    totalUsers: 25,
    totalPages: 1,
    searchQuery: '',
    includeDeleted: false,
    setPage: mockSetPage,
    setSearchQuery: mockSetSearchQuery,
    setIncludeDeleted: mockSetIncludeDeleted,
    getUserDetails: mockGetUserDetails,
    anonymizeUser: mockAnonymizeUser,
    fetchUsers: vi.fn(),
    refresh: vi.fn(),
    setPageSize: vi.fn(),
    pageSize: 50,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAdminUsers).mockReturnValue(defaultMockHook)
    mockGetUserDetails.mockResolvedValue(mockUserDetail)
    mockAnonymizeUser.mockResolvedValue({
      success: true,
      message: 'User anonymized successfully',
      user_id: 'user-1',
    })
  })

  describe('rendering', () => {
    it('should render page header and search elements', () => {
      render(<AdminUsers />)

      expect(screen.getByText('User Management')).toBeInTheDocument()
      expect(screen.getByText('View and manage all users in the system')).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/search by email, phone/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/include deleted users/i)).toBeInTheDocument()
    })

    it('should display user count', () => {
      render(<AdminUsers />)

      expect(screen.getByText(/Showing 2 of 25 users/i)).toBeInTheDocument()
      expect(screen.getByText(/Page 1 of 1/i)).toBeInTheDocument()
    })

    it('should render user table with data', () => {
      render(<AdminUsers />)

      expect(screen.getByText('user1@example.com')).toBeInTheDocument()
      expect(screen.getByText('+442012345678')).toBeInTheDocument()
    })
  })

  describe('search functionality', () => {
    it('should call setSearchQuery when search input changes', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      const searchInput = screen.getByPlaceholderText(/search by email, phone/i)
      await user.type(searchInput, 't')

      // setSearchQuery is called for each character typed
      expect(mockSetSearchQuery).toHaveBeenCalled()
    })
  })

  describe('filter functionality', () => {
    it('should call setIncludeDeleted when checkbox is toggled', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      const checkbox = screen.getByLabelText(/include deleted users/i)
      await user.click(checkbox)

      expect(mockSetIncludeDeleted).toHaveBeenCalledWith(true)
    })
  })

  describe('pagination', () => {
    it('should not display pagination when there is only one page', () => {
      render(<AdminUsers />)

      // With totalPages = 1, pagination should not be rendered
      expect(screen.queryByRole('link', { name: /previous/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /next/i })).not.toBeInTheDocument()
    })

    it('should display pagination when there are multiple pages', () => {
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 3,
        currentPage: 2,
      })

      render(<AdminUsers />)

      // Should show previous and next  buttons
      const navigation = screen.getByRole('navigation')
      expect(navigation).toBeInTheDocument()
    })

    it('should call setPage when page link is clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 3,
        currentPage: 1,
      })

      render(<AdminUsers />)

      // Find page 2 link by text content within navigation
      const navigation = screen.getByRole('navigation')
      const page2Link = within(navigation).getByText('2')

      await user.click(page2Link)
      expect(mockSetPage).toHaveBeenCalledWith(2)
    })

    it('should call setPage when Previous button clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 3,
        currentPage: 2,
      })

      render(<AdminUsers />)

      const navigation = screen.getByRole('navigation')
      const prevButton = within(navigation).getByText('Previous')

      await user.click(prevButton)
      expect(mockSetPage).toHaveBeenCalledWith(1)
    })

    it('should call setPage when Next button clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 3,
        currentPage: 1,
      })

      render(<AdminUsers />)

      const navigation = screen.getByRole('navigation')
      const nextButton = within(navigation).getByText('Next')

      await user.click(nextButton)
      expect(mockSetPage).toHaveBeenCalledWith(2)
    })

    it('should show ellipsis for many pages', () => {
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 10,
        currentPage: 5,
      })

      render(<AdminUsers />)

      const navigation = screen.getByRole('navigation')
      // Should show ellipsis (represented as "...")
      const ellipses = within(navigation).getAllByText('...')
      expect(ellipses.length).toBeGreaterThan(0)
    })

    it('should handle pagination on last page', () => {
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 10,
        currentPage: 10,
      })

      render(<AdminUsers />)

      const navigation = screen.getByRole('navigation')
      // Should show page 10
      expect(within(navigation).getByText('10')).toBeInTheDocument()
    })

    it('should show all pages when totalPages <= 5', () => {
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        totalPages: 4,
        currentPage: 2,
      })

      render(<AdminUsers />)

      const navigation = screen.getByRole('navigation')
      // Should show all 4 pages
      expect(within(navigation).getByText('1')).toBeInTheDocument()
      expect(within(navigation).getByText('2')).toBeInTheDocument()
      expect(within(navigation).getByText('3')).toBeInTheDocument()
      expect(within(navigation).getByText('4')).toBeInTheDocument()
    })
  })

  describe('user details dialog', () => {
    it('should open user details dialog when view button clicked', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      const viewButton = screen.getAllByRole('button', { name: /view/i })[0]
      await user.click(viewButton)

      await waitFor(() => {
        expect(screen.getByText('User Details')).toBeInTheDocument()
      })

      expect(mockGetUserDetails).toHaveBeenCalledWith('user-1')
    })

    it('should close user details dialog when close button clicked', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      // Open dialog
      const viewButton = screen.getAllByRole('button', { name: /view/i })[0]
      await user.click(viewButton)

      await waitFor(() => {
        expect(screen.getByText('User Details')).toBeInTheDocument()
      })

      // Close dialog - get all close buttons and use the last one (footer button)
      const closeButtons = screen.getAllByRole('button', { name: /close/i })
      await user.click(closeButtons[closeButtons.length - 1])

      await waitFor(() => {
        expect(screen.queryByText('User Details')).not.toBeInTheDocument()
      })
    })
  })

  describe('anonymize dialog', () => {
    it('should open anonymize dialog when anonymize button clicked', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      const anonymizeButton = screen.getAllByRole('button', { name: /anonymize/i })[0]
      await user.click(anonymizeButton)

      await waitFor(() => {
        expect(screen.getByText(/Anonymize User/i)).toBeInTheDocument()
      })
    })

    it('should anonymize user and show success toast when confirmed', async () => {
      const user = userEvent.setup()
      render(<AdminUsers />)

      // Open anonymize dialog
      const anonymizeButton = screen.getAllByRole('button', { name: /anonymize/i })[0]
      await user.click(anonymizeButton)

      await waitFor(() => {
        expect(screen.getByPlaceholderText('ANONYMIZE')).toBeInTheDocument()
      })

      // Type confirmation
      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'ANONYMIZE')

      // Confirm
      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockAnonymizeUser).toHaveBeenCalledWith('user-1')
        expect(toast.success).toHaveBeenCalledWith('User anonymized successfully')
      })
    })

    it('should show error toast when anonymization fails', async () => {
      const user = userEvent.setup()
      mockAnonymizeUser.mockRejectedValue(new Error('Failed to anonymize'))

      render(<AdminUsers />)

      // Open anonymize dialog
      const anonymizeButton = screen.getAllByRole('button', { name: /anonymize/i })[0]
      await user.click(anonymizeButton)

      await waitFor(() => {
        expect(screen.getByPlaceholderText('ANONYMIZE')).toBeInTheDocument()
      })

      // Type confirmation and confirm
      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'ANONYMIZE')

      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Failed to anonymize')
      })
    })
  })

  describe('error handling', () => {
    it('should display error alert when there is an error', () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        error: mockError,
      })

      render(<AdminUsers />)

      expect(screen.getByText(/Internal Server Error/i)).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('should pass loading state to user table', () => {
      vi.mocked(useAdminUsers).mockReturnValue({
        ...defaultMockHook,
        loading: true,
        users: null,
      })

      render(<AdminUsers />)

      // Table should show skeleton loaders (checked in UserTable.test.tsx)
      const skeletons = document.querySelectorAll('.animate-pulse')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })
})
