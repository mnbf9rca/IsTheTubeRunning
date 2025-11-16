import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AnonymizeUserDialog } from './AnonymizeUserDialog'

describe('AnonymizeUserDialog', () => {
  const mockOnOpenChange = vi.fn()
  const mockOnConfirm = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockOnConfirm.mockResolvedValue(undefined)
  })

  describe('rendering', () => {
    it('should not render when open is false', () => {
      const { container } = render(
        <AnonymizeUserDialog
          userId={null}
          open={false}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      expect(container).toBeEmptyDOMElement()
    })

    it('should display warning message and instructions', () => {
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      expect(screen.getByText(/Anonymize User/i)).toBeInTheDocument()
      expect(screen.getByText(/This action is/i)).toBeInTheDocument()
      expect(screen.getByText(/irreversible/i)).toBeInTheDocument()
      expect(screen.getByText(/Remove all email addresses/i)).toBeInTheDocument()
      expect(screen.getByText(/Remove all phone numbers/i)).toBeInTheDocument()
    })

    it('should show confirmation input field', () => {
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      expect(input).toBeInTheDocument()
      expect(input).toHaveValue('')
    })
  })

  describe('confirmation input validation', () => {
    it('should disable confirm button when input is empty', () => {
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      expect(confirmButton).toBeDisabled()
    })

    it('should disable confirm button when input does not match', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'WRONG')

      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      expect(confirmButton).toBeDisabled()
    })

    it('should show error message when input does not match', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'anonymize')

      expect(screen.getByText(/Please type "ANONYMIZE" exactly as shown/i)).toBeInTheDocument()
    })

    it('should enable confirm button when input matches exactly', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'ANONYMIZE')

      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      expect(confirmButton).not.toBeDisabled()
    })
  })

  describe('actions', () => {
    it('should call onOpenChange when cancel button clicked', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      expect(mockOnOpenChange).toHaveBeenCalledWith(false)
      expect(mockOnConfirm).not.toHaveBeenCalled()
    })

    it('should call onConfirm and close when confirm button clicked with correct input', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'ANONYMIZE')

      const confirmButton = screen.getByRole('button', { name: /confirm anonymization/i })
      await user.click(confirmButton)

      await waitFor(() => {
        expect(mockOnConfirm).toHaveBeenCalledWith('user-1')
        expect(mockOnOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it('should reset state via onOpenChange callback pattern', async () => {
      const user = userEvent.setup()
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      await user.type(input, 'ANONYMIZE')
      expect(input).toHaveValue('ANONYMIZE')

      // Click cancel which calls onOpenChange
      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      expect(mockOnOpenChange).toHaveBeenCalledWith(false)
    })
  })

  describe('loading state', () => {
    it('should disable buttons and show loading text when loading', () => {
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
          loading={true}
        />
      )

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      const confirmButton = screen.getByRole('button', { name: /anonymizing/i })

      expect(cancelButton).toBeDisabled()
      expect(confirmButton).toBeDisabled()
      expect(confirmButton).toHaveTextContent('Anonymizing...')
    })

    it('should disable input field when loading', () => {
      render(
        <AnonymizeUserDialog
          userId="user-1"
          open={true}
          onOpenChange={mockOnOpenChange}
          onConfirm={mockOnConfirm}
          loading={true}
        />
      )

      const input = screen.getByPlaceholderText('ANONYMIZE')
      expect(input).toBeDisabled()
    })
  })
})
