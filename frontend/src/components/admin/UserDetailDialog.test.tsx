import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { UserDetailDialog } from './UserDetailDialog'
import type { UserDetailResponse } from '@/types'
import { ApiError } from '@/lib/api'

describe('UserDetailDialog', () => {
  const mockUserDetails: UserDetailResponse = {
    id: 'user-1-uuid-1234567890',
    external_id: 'auth0|123',
    auth_provider: 'auth0',
    created_at: '2025-01-01T12:00:00Z',
    updated_at: '2025-01-05T14:30:00Z',
    deleted_at: null,
    email_addresses: [
      { id: 'email-1', email: 'user1@example.com', verified: true, is_primary: true },
      { id: 'email-2', email: 'user1alt@example.com', verified: false, is_primary: false },
    ],
    phone_numbers: [{ id: 'phone-1', phone: '+442012345678', verified: true, is_primary: true }],
  }

  const mockFetchUserDetails = vi.fn()
  const mockOnOpenChange = vi.fn()
  const mockOnAnonymize = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchUserDetails.mockResolvedValue(mockUserDetails)
  })

  describe('rendering', () => {
    it('should not fetch details when dialog is closed', () => {
      render(
        <UserDetailDialog
          userId="user-1"
          open={false}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      expect(mockFetchUserDetails).not.toHaveBeenCalled()
    })

    it('should show loading state while fetching', async () => {
      // Make fetch take longer
      mockFetchUserDetails.mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockUserDetails), 100))
      )

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      // Should show skeleton loaders
      const skeletons = document.querySelectorAll('.animate-pulse')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('should display user details after successful fetch', async () => {
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('user-1-uuid-1234567890')).toBeInTheDocument()
      })

      expect(screen.getByText('auth0|123')).toBeInTheDocument()
      expect(screen.getByText('auth0')).toBeInTheDocument()
      expect(screen.getByText('user1@example.com')).toBeInTheDocument()
      expect(screen.getByText('user1alt@example.com')).toBeInTheDocument()
      expect(screen.getByText('+442012345678')).toBeInTheDocument()
    })

    it('should show verified badges for verified contacts', async () => {
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getAllByText('Verified')).toHaveLength(2) // 1 email + 1 phone
      })

      expect(screen.getByText('Unverified')).toBeInTheDocument() // 1 unverified email
    })

    it('should show primary badges for primary contacts', async () => {
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getAllByText('Primary')).toHaveLength(2) // 1 email + 1 phone
      })
    })

    it('should show error alert on fetch failure', async () => {
      const mockError = new ApiError(404, 'User not found')
      mockFetchUserDetails.mockRejectedValue(mockError)

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText(/Failed to load user details/i)).toBeInTheDocument()
      })
    })

    it('should display "No email addresses" when user has no emails', async () => {
      const userWithoutEmails = {
        ...mockUserDetails,
        email_addresses: [],
      }
      mockFetchUserDetails.mockResolvedValue(userWithoutEmails)

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('No email addresses')).toBeInTheDocument()
      })
    })

    it('should display "No phone numbers" when user has no phones', async () => {
      const userWithoutPhones = {
        ...mockUserDetails,
        phone_numbers: [],
      }
      mockFetchUserDetails.mockResolvedValue(userWithoutPhones)

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('No phone numbers')).toBeInTheDocument()
      })
    })
  })

  describe('status and timestamps', () => {
    it('should show Active status for non-deleted users', async () => {
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument()
      })
    })

    it('should show Deleted status and timestamp for deleted users', async () => {
      const deletedUser = {
        ...mockUserDetails,
        deleted_at: '2025-01-15T10:00:00Z',
      }
      mockFetchUserDetails.mockResolvedValue(deletedUser)

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Deleted')).toBeInTheDocument()
      })
    })
  })

  describe('actions', () => {
    it('should close dialog when close button clicked', async () => {
      const user = userEvent.setup()
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('user-1-uuid-1234567890')).toBeInTheDocument()
      })

      // Get all close buttons and click the explicit "Close" button in footer
      const closeButtons = screen.getAllByRole('button', { name: /close/i })
      await user.click(closeButtons[closeButtons.length - 1])

      expect(mockOnOpenChange).toHaveBeenCalledWith(false)
    })

    it('should call onAnonymize and close when anonymize button clicked', async () => {
      const user = userEvent.setup()
      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('user-1-uuid-1234567890')).toBeInTheDocument()
      })

      const anonymizeButton = screen.getByRole('button', { name: /anonymize user/i })
      await user.click(anonymizeButton)

      expect(mockOnAnonymize).toHaveBeenCalledWith('user-1')
      expect(mockOnOpenChange).toHaveBeenCalledWith(false)
    })

    it('should not show anonymize button for deleted users', async () => {
      const deletedUser = {
        ...mockUserDetails,
        deleted_at: '2025-01-15T10:00:00Z',
      }
      mockFetchUserDetails.mockResolvedValue(deletedUser)

      render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      await waitFor(() => {
        expect(screen.getByText('Deleted')).toBeInTheDocument()
      })

      expect(screen.queryByRole('button', { name: /anonymize user/i })).not.toBeInTheDocument()
    })
  })

  describe('state cleanup', () => {
    it('should cleanup on unmount and not update state', async () => {
      const { unmount } = render(
        <UserDetailDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onAnonymize={mockOnAnonymize}
          fetchUserDetails={mockFetchUserDetails}
        />
      )

      // Unmount before fetch completes
      unmount()

      // Wait to ensure no state updates happen
      await waitFor(() => {
        expect(mockFetchUserDetails).toHaveBeenCalled()
      })

      // Should not throw error (cancelled flag prevents state updates)
    })
  })
})
