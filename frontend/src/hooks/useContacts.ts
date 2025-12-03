import { useState, useEffect, useCallback } from 'react'
import type { ContactsResponse, EmailResponse, PhoneResponse } from '@/types'
import {
  ApiError,
  getContacts as apiGetContacts,
  addEmail as apiAddEmail,
  addPhone as apiAddPhone,
  sendVerification as apiSendVerification,
  verifyCode as apiVerifyCode,
  deleteContact as apiDeleteContact,
} from '../lib/api'

export interface UseContactsReturn {
  // State
  contacts: ContactsResponse | null
  loading: boolean
  error: ApiError | null

  // Actions
  addEmail: (email: string) => Promise<EmailResponse>
  addPhone: (phone: string) => Promise<PhoneResponse>
  sendVerification: (contactId: string) => Promise<void>
  verifyCode: (contactId: string, code: string) => Promise<void>
  deleteContact: (contactId: string) => Promise<void>
  refresh: () => Promise<void>

  // Rate limit tracking (client-side hints)
  verificationAttempts: Record<string, number>
  canResendVerification: (contactId: string) => boolean
}

const MAX_VERIFICATION_ATTEMPTS = 3

/**
 * Hook for managing contacts (emails and phones) with verification
 *
 * This hook provides state management and API interactions for contact management.
 * It tracks verification attempts client-side to provide UI hints about rate limits,
 * though the server enforces all rate limits authoritatively.
 *
 * @returns UseContactsReturn object with state and action methods
 *
 * @example
 * const { contacts, loading, addEmail, sendVerification, verifyCode } = useContacts()
 *
 * // Add email
 * const email = await addEmail('user@example.com')
 *
 * // Send verification code
 * await sendVerification(email.id)
 *
 * // Verify with code
 * await verifyCode(email.id, '123456')
 */
export function useContacts(): UseContactsReturn {
  const [contacts, setContacts] = useState<ContactsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [verificationAttempts, setVerificationAttempts] = useState<Record<string, number>>({})

  /**
   * Fetch contacts from API
   */
  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiGetContacts()
      setContacts(data)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * Initial fetch on mount
   */
  useEffect(() => {
    refresh().catch(() => {
      // Error already set in state
    })
  }, [refresh])

  /**
   * Add a new email address
   */
  const addEmail = useCallback(
    async (email: string): Promise<EmailResponse> => {
      try {
        setError(null)
        const newEmail = await apiAddEmail(email)
        // Refresh to get updated list
        await refresh()
        return newEmail
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Add a new phone number
   */
  const addPhone = useCallback(
    async (phone: string): Promise<PhoneResponse> => {
      try {
        setError(null)
        const newPhone = await apiAddPhone(phone)
        // Refresh to get updated list
        await refresh()
        return newPhone
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Send verification code to a contact
   *
   * Tracks attempts client-side for UI hints (max 3 per contact)
   */
  const sendVerification = useCallback(async (contactId: string): Promise<void> => {
    try {
      setError(null)
      await apiSendVerification(contactId)

      // Track attempt for UI hints
      setVerificationAttempts((prev) => ({
        ...prev,
        [contactId]: (prev[contactId] || 0) + 1,
      }))
    } catch (err) {
      setError(err as ApiError)
      throw err
    }
  }, [])

  /**
   * Verify a contact with the provided code
   *
   * Resets verification attempts on success
   */
  const verifyCode = useCallback(
    async (contactId: string, code: string): Promise<void> => {
      try {
        setError(null)
        await apiVerifyCode(contactId, code)

        // Reset attempts on successful verification
        setVerificationAttempts((prev) => {
          const newAttempts = { ...prev }
          delete newAttempts[contactId]
          return newAttempts
        })

        // Refresh to get updated verified status
        await refresh()
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Delete a contact
   */
  const deleteContact = useCallback(
    async (contactId: string): Promise<void> => {
      try {
        setError(null)
        await apiDeleteContact(contactId)

        // Clear verification attempts for deleted contact
        setVerificationAttempts((prev) => {
          const newAttempts = { ...prev }
          delete newAttempts[contactId]
          return newAttempts
        })

        // Refresh to get updated list
        await refresh()
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Check if resend verification is allowed (client-side hint)
   *
   * Server enforces actual rate limit of 3 per hour
   */
  const canResendVerification = useCallback(
    (contactId: string): boolean => {
      const attempts = verificationAttempts[contactId] || 0
      return attempts < MAX_VERIFICATION_ATTEMPTS
    },
    [verificationAttempts]
  )

  return {
    contacts,
    loading,
    error,
    addEmail,
    addPhone,
    sendVerification,
    verifyCode,
    deleteContact,
    refresh,
    verificationAttempts,
    canResendVerification,
  }
}
