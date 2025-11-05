import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useContacts } from './useContacts'
import { ApiError } from '../lib/api'
import type { ContactsResponse, EmailResponse, PhoneResponse } from '../lib/api'

// Mock the API module
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    getContacts: vi.fn(),
    addEmail: vi.fn(),
    addPhone: vi.fn(),
    sendVerification: vi.fn(),
    verifyCode: vi.fn(),
    deleteContact: vi.fn(),
  }
})

// Import mocked functions
import * as api from '../lib/api'

describe('useContacts', () => {
  const mockContactsResponse: ContactsResponse = {
    emails: [
      {
        id: 'email-1',
        email: 'test@example.com',
        verified: true,
        is_primary: true,
        created_at: '2025-01-01T00:00:00Z',
      },
    ],
    phones: [
      {
        id: 'phone-1',
        phone: '+442012345678',
        verified: false,
        is_primary: false,
        created_at: '2025-01-01T00:00:00Z',
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock implementation
    vi.mocked(api.getContacts).mockResolvedValue(mockContactsResponse)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initialization', () => {
    it('should fetch contacts on mount', async () => {
      const { result } = renderHook(() => useContacts())

      // Initially loading
      expect(result.current.loading).toBe(true)
      expect(result.current.contacts).toBeNull()

      // Wait for fetch to complete
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.contacts).toEqual(mockContactsResponse)
      expect(result.current.error).toBeNull()
      expect(api.getContacts).toHaveBeenCalledTimes(1)
    })

    it('should handle fetch error on mount', async () => {
      const mockError = new ApiError(500, 'Internal Server Error')
      vi.mocked(api.getContacts).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(result.current.contacts).toBeNull()
      expect(result.current.error).toEqual(mockError)
    })
  })

  describe('addEmail', () => {
    it('should add email and refresh contacts', async () => {
      const newEmail: EmailResponse = {
        id: 'email-2',
        email: 'new@example.com',
        verified: false,
        is_primary: false,
        created_at: '2025-01-02T00:00:00Z',
      }

      vi.mocked(api.addEmail).mockResolvedValue(newEmail)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Add email
      let addedEmail: EmailResponse | undefined
      await waitFor(async () => {
        addedEmail = await result.current.addEmail('new@example.com')
      })

      expect(addedEmail).toEqual(newEmail)
      expect(api.addEmail).toHaveBeenCalledWith('new@example.com')
      expect(api.getContacts).toHaveBeenCalledTimes(2) // Initial + refresh
    })

    it('should handle 409 conflict error', async () => {
      const mockError = new ApiError(409, 'Conflict', {
        detail: 'Email already registered',
      })
      vi.mocked(api.addEmail).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Try to add duplicate email - catch error to prevent unhandled rejection
      await waitFor(async () => {
        try {
          await result.current.addEmail('test@example.com')
          // Should not reach here
          expect(true).toBe(false)
        } catch (err) {
          expect(err).toBeInstanceOf(ApiError)
          expect((err as ApiError).status).toBe(409)
        }
      })

      // Error should be set in state
      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })

    it('should handle 429 rate limit error', async () => {
      const mockError = new ApiError(429, 'Too Many Requests')
      vi.mocked(api.addEmail).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.addEmail('test@example.com')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(429)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('addPhone', () => {
    it('should add phone and refresh contacts', async () => {
      const newPhone: PhoneResponse = {
        id: 'phone-2',
        phone: '+447700900000',
        verified: false,
        is_primary: false,
        created_at: '2025-01-02T00:00:00Z',
      }

      vi.mocked(api.addPhone).mockResolvedValue(newPhone)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      // Add phone
      let addedPhone: PhoneResponse | undefined
      await waitFor(async () => {
        addedPhone = await result.current.addPhone('+447700900000')
      })

      expect(addedPhone).toEqual(newPhone)
      expect(api.addPhone).toHaveBeenCalledWith('+447700900000')
      expect(api.getContacts).toHaveBeenCalledTimes(2)
    })

    it('should handle 400 invalid format error', async () => {
      const mockError = new ApiError(400, 'Bad Request', {
        detail: 'Invalid phone format',
      })
      vi.mocked(api.addPhone).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.addPhone('invalid')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(400)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('sendVerification', () => {
    it('should send verification code and track attempts', async () => {
      vi.mocked(api.sendVerification).mockResolvedValue({
        success: true,
        message: 'Code sent',
      })

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const contactId = 'email-1'

      // Initially can resend
      expect(result.current.canResendVerification(contactId)).toBe(true)
      expect(result.current.verificationAttempts[contactId]).toBeUndefined()

      // Send verification
      await waitFor(async () => {
        await result.current.sendVerification(contactId)
      })

      expect(api.sendVerification).toHaveBeenCalledWith(contactId)

      // Wait for state update
      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBe(1)
      })

      expect(result.current.canResendVerification(contactId)).toBe(true)
    })

    it('should track multiple attempts and block after 3', async () => {
      vi.mocked(api.sendVerification).mockResolvedValue({
        success: true,
        message: 'Code sent',
      })

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const contactId = 'email-1'

      // Send 3 times
      await waitFor(async () => {
        await result.current.sendVerification(contactId)
        await result.current.sendVerification(contactId)
        await result.current.sendVerification(contactId)
      })

      // Wait for state updates
      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBe(3)
      })

      expect(result.current.canResendVerification(contactId)).toBe(false)
    })

    it('should handle 404 contact not found', async () => {
      const mockError = new ApiError(404, 'Not Found')
      vi.mocked(api.sendVerification).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.sendVerification('nonexistent')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(404)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })

    it('should handle 429 rate limit (server)', async () => {
      const mockError = new ApiError(429, 'Too Many Requests')
      vi.mocked(api.sendVerification).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.sendVerification('email-1')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(429)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('verifyCode', () => {
    it('should verify code, reset attempts, and refresh', async () => {
      vi.mocked(api.sendVerification).mockResolvedValue({
        success: true,
        message: 'Code sent',
      })
      vi.mocked(api.verifyCode).mockResolvedValue({
        success: true,
        message: 'Verified',
      })

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const contactId = 'email-1'

      // Send verification first to track attempts
      await waitFor(async () => {
        await result.current.sendVerification(contactId)
      })

      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBe(1)
      })

      // Verify code
      await waitFor(async () => {
        await result.current.verifyCode(contactId, '123456')
      })

      expect(api.verifyCode).toHaveBeenCalledWith(contactId, '123456')

      // Wait for state update
      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBeUndefined() // Reset
      })

      expect(api.getContacts).toHaveBeenCalledTimes(2) // Initial + refresh
    })

    it('should handle 400 invalid code', async () => {
      const mockError = new ApiError(400, 'Bad Request', {
        detail: 'Invalid verification code',
      })
      vi.mocked(api.verifyCode).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.verifyCode('email-1', 'wrong')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(400)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })

    it('should handle 400 expired code', async () => {
      const mockError = new ApiError(400, 'Bad Request', {
        detail: 'Verification code has expired',
      })
      vi.mocked(api.verifyCode).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.verifyCode('email-1', '123456')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(400)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('deleteContact', () => {
    it('should delete contact, clear attempts, and refresh', async () => {
      vi.mocked(api.sendVerification).mockResolvedValue({
        success: true,
        message: 'Code sent',
      })
      vi.mocked(api.deleteContact).mockResolvedValue(undefined)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const contactId = 'email-1'

      // Send verification first to track attempts
      await waitFor(async () => {
        await result.current.sendVerification(contactId)
      })

      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBe(1)
      })

      // Delete contact
      await waitFor(async () => {
        await result.current.deleteContact(contactId)
      })

      expect(api.deleteContact).toHaveBeenCalledWith(contactId)

      // Wait for state update
      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBeUndefined() // Cleared
      })

      expect(api.getContacts).toHaveBeenCalledTimes(2) // Initial + refresh
    })

    it('should handle 404 contact not found', async () => {
      const mockError = new ApiError(404, 'Not Found')
      vi.mocked(api.deleteContact).mockRejectedValue(mockError)

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      try {
        await result.current.deleteContact('nonexistent')
        expect(true).toBe(false)
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(404)
      }

      await waitFor(() => {
        expect(result.current.error).toEqual(mockError)
      })
    })
  })

  describe('refresh', () => {
    it('should manually refresh contacts', async () => {
      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      expect(api.getContacts).toHaveBeenCalledTimes(1)

      // Manually refresh
      await result.current.refresh()

      expect(api.getContacts).toHaveBeenCalledTimes(2)
    })
  })

  describe('canResendVerification', () => {
    it('should return true when attempts < 3', () => {
      const { result } = renderHook(() => useContacts())

      expect(result.current.canResendVerification('any-id')).toBe(true)
    })

    it('should return false when attempts >= 3', async () => {
      vi.mocked(api.sendVerification).mockResolvedValue({
        success: true,
        message: 'Code sent',
      })

      const { result } = renderHook(() => useContacts())

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })

      const contactId = 'test-id'

      // Send 3 times to hit limit
      await waitFor(async () => {
        await result.current.sendVerification(contactId)
        await result.current.sendVerification(contactId)
        await result.current.sendVerification(contactId)
      })

      // Wait for state update
      await waitFor(() => {
        expect(result.current.verificationAttempts[contactId]).toBe(3)
      })

      expect(result.current.canResendVerification(contactId)).toBe(false)
    })
  })
})
