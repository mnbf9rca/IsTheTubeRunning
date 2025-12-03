import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { UserTable } from './UserTable'
import type { UserListItem } from '@/types'

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { toast } from 'sonner'

describe('UserTable', () => {
  const mockUsers: UserListItem[] = [
    {
      id: 'user-1-uuid-1234567890',
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
      id: 'user-2-uuid-9876543210',
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
  ]

  const mockOnViewDetails = vi.fn()
  const mockOnAnonymize = vi.fn()
  let writeTextMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock clipboard API - preserve navigator but stub clipboard
    writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(global.navigator, 'clipboard', {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    })
  })

  describe('rendering', () => {
    it('should render user list correctly', () => {
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      // Check that table contains user data (IDs are truncated, so check by title attribute)
      const table = screen.getByRole('table')
      expect(table).toBeInTheDocument()

      // Check providers
      expect(screen.getAllByText('auth0')).toHaveLength(2)

      // Check emails/phones
      expect(screen.getByText('user1@example.com')).toBeInTheDocument()
      expect(screen.getByText('+442012345678')).toBeInTheDocument()

      // Check external IDs are displayed
      expect(screen.getByText('auth0|123')).toBeInTheDocument()
      expect(screen.getByText('auth0|456')).toBeInTheDocument()
    })

    it('should show verified badges for verified contacts', () => {
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      // User 1 has verified email - should show CheckCircle
      const emailRow = screen.getByText('user1@example.com').closest('div')
      expect(emailRow?.querySelector('svg')).toBeInTheDocument()

      // User 2 has unverified phone - should show XCircle
      const phoneRow = screen.getByText('+442012345678').closest('div')
      expect(phoneRow?.querySelector('svg')).toBeInTheDocument()
    })

    it('should show "None" for users without contacts', () => {
      const userWithoutContacts: UserListItem = {
        ...mockUsers[0],
        email_addresses: [],
        phone_numbers: [],
      }

      render(
        <UserTable
          users={[userWithoutContacts]}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      expect(screen.getAllByText('None')).toHaveLength(2) // One for emails, one for phones
    })

    it('should render status badges correctly', () => {
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      expect(screen.getByText('Active')).toBeInTheDocument()
      expect(screen.getByText('Deleted')).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('should show skeleton loaders when loading', () => {
      render(
        <UserTable
          users={[]}
          loading={true}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      // Should show 5 skeleton loaders
      const skeletons = document.querySelectorAll('.animate-pulse')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('empty state', () => {
    it('should show empty state when no users', () => {
      render(
        <UserTable
          users={[]}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      expect(screen.getByText('No users found')).toBeInTheDocument()
      expect(screen.getByText('Try adjusting your search or filters')).toBeInTheDocument()
    })
  })

  describe('copy ID functionality', () => {
    it('should copy user ID to clipboard and show success toast', async () => {
      const user = userEvent.setup()
      // Re-setup mock before render to ensure it's fresh
      const freshWriteTextMock = vi.fn().mockResolvedValue(undefined)
      Object.defineProperty(global.navigator, 'clipboard', {
        value: {
          writeText: freshWriteTextMock,
        },
        writable: true,
        configurable: true,
      })

      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      const copyButtons = screen.getAllByTitle('Copy full UUID')
      await user.click(copyButtons[0])

      await waitFor(() => {
        expect(freshWriteTextMock).toHaveBeenCalledWith('user-1-uuid-1234567890')
        expect(toast.success).toHaveBeenCalledWith('User ID copied to clipboard')
      })
    })

    it('should show error toast if clipboard copy fails', async () => {
      const user = userEvent.setup()
      // Mock clipboard failure
      const failingWriteTextMock = vi.fn().mockRejectedValue(new Error('Clipboard error'))
      Object.defineProperty(global.navigator, 'clipboard', {
        value: {
          writeText: failingWriteTextMock,
        },
        writable: true,
        configurable: true,
      })

      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      const copyButtons = screen.getAllByTitle('Copy full UUID')
      await user.click(copyButtons[0])

      await waitFor(() => {
        expect(failingWriteTextMock).toHaveBeenCalledWith('user-1-uuid-1234567890')
        expect(toast.error).toHaveBeenCalledWith('Failed to copy ID to clipboard')
      })
    })
  })

  describe('action buttons', () => {
    it('should call onViewDetails when view button clicked', async () => {
      const user = userEvent.setup()
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      const viewButtons = screen.getAllByRole('button', { name: /view/i })
      await user.click(viewButtons[0])

      expect(mockOnViewDetails).toHaveBeenCalledWith('user-1-uuid-1234567890')
      expect(mockOnViewDetails).toHaveBeenCalledTimes(1)
    })

    it('should call onAnonymize when anonymize button clicked', async () => {
      const user = userEvent.setup()
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      // Click anonymize button for first user (active user)
      const anonymizeButtons = screen.getAllByRole('button', { name: /anonymize/i })
      await user.click(anonymizeButtons[0])

      expect(mockOnAnonymize).toHaveBeenCalledWith('user-1-uuid-1234567890')
      expect(mockOnAnonymize).toHaveBeenCalledTimes(1)
    })

    it('should disable anonymize button for deleted users', () => {
      render(
        <UserTable
          users={mockUsers}
          loading={false}
          onViewDetails={mockOnViewDetails}
          onAnonymize={mockOnAnonymize}
        />
      )

      const anonymizeButtons = screen.getAllByRole('button', { name: /anonymize/i })

      // First user (active) - button should be enabled
      expect(anonymizeButtons[0]).not.toBeDisabled()

      // Second user (deleted) - button should be disabled
      expect(anonymizeButtons[1]).toBeDisabled()
      expect(anonymizeButtons[1]).toHaveAttribute('title', 'Already anonymized')
    })
  })
})
