import { useState } from 'react'
import type { Contact } from '@/types'
import type { UseContactsReturn } from './useContacts'

/**
 * Custom hook to manage dialog state and orchestration for the Contacts page
 *
 * Extracts complex state management and dialog flow logic to keep the
 * Contacts component focused on presentation.
 */
export function useContactDialogs(contactsHook: UseContactsReturn) {
  const { contacts, sendVerification } = contactsHook

  // Dialog states
  const [addEmailOpen, setAddEmailOpen] = useState(false)
  const [addPhoneOpen, setAddPhoneOpen] = useState(false)
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false)
  const [verifyingContact, setVerifyingContact] = useState<Contact | null>(null)
  const [verifyingType, setVerifyingType] = useState<'email' | 'phone'>('email')

  // Action loading states
  const [deletingId, setDeletingId] = useState<string | undefined>(undefined)

  /**
   * Open verification dialog for a specific contact
   */
  const openVerifyDialog = async (id: string, type: 'email' | 'phone') => {
    const contact =
      type === 'email'
        ? contacts?.emails.find((e) => e.id === id)
        : contacts?.phones.find((p) => p.id === id)

    if (!contact) return

    setVerifyingContact(contact)
    setVerifyingType(type)
    setVerifyDialogOpen(true)

    // Auto-send verification code
    return await sendVerification(id)
  }

  /**
   * Open add email dialog and auto-open verification on success
   */
  const openAddEmailFlow = async (contact: Contact) => {
    setVerifyingContact(contact)
    setVerifyingType('email')
    setVerifyDialogOpen(true)
    setAddEmailOpen(false)

    // Auto-send verification code
    return await sendVerification(contact.id)
  }

  /**
   * Open add phone dialog and auto-open verification on success
   */
  const openAddPhoneFlow = async (contact: Contact) => {
    setVerifyingContact(contact)
    setVerifyingType('phone')
    setVerifyDialogOpen(true)
    setAddPhoneOpen(false)

    // Auto-send verification code
    return await sendVerification(contact.id)
  }

  /**
   * Close verification dialog
   */
  const closeVerifyDialog = () => {
    setVerifyDialogOpen(false)
    setVerifyingContact(null)
  }

  /**
   * Track deletion loading state
   */
  const startDelete = (id: string) => setDeletingId(id)
  const endDelete = () => setDeletingId(undefined)

  return {
    // Dialog states
    addEmailOpen,
    setAddEmailOpen,
    addPhoneOpen,
    setAddPhoneOpen,
    verifyDialogOpen,
    verifyingContact,
    verifyingType,

    // Action states
    deletingId,

    // Dialog actions
    openVerifyDialog,
    openAddEmailFlow,
    openAddPhoneFlow,
    closeVerifyDialog,
    startDelete,
    endDelete,
  }
}
