import { useState } from 'react'
import { Mail, Phone, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { ContactList } from '../components/contacts/ContactList'
import { AddContactDialog } from '../components/contacts/AddContactDialog'
import { VerificationDialog } from '../components/contacts/VerificationDialog'
import { useContacts } from '../hooks/useContacts'
import type { Contact } from '../lib/api'

/**
 * Contacts page for managing email addresses and phone numbers
 *
 * Allows users to:
 * - Add email addresses and phone numbers
 * - Verify contacts with 6-digit codes
 * - Delete contacts
 * - View verification status and primary contacts
 */
export function Contacts() {
  const {
    contacts,
    loading,
    addEmail,
    addPhone,
    sendVerification,
    verifyCode,
    deleteContact,
    canResendVerification,
  } = useContacts()

  // Dialog states
  const [addEmailOpen, setAddEmailOpen] = useState(false)
  const [addPhoneOpen, setAddPhoneOpen] = useState(false)
  const [verifyDialogOpen, setVerifyDialogOpen] = useState(false)
  const [verifyingContact, setVerifyingContact] = useState<Contact | null>(null)
  const [verifyingType, setVerifyingType] = useState<'email' | 'phone'>('email')

  // Action loading states
  const [deletingId, setDeletingId] = useState<string | undefined>(undefined)

  /**
   * Handle adding a new email address
   */
  const handleAddEmail = async (email: string) => {
    const result = await addEmail(email)
    toast.success(`Email added: ${result.email}`, {
      description: 'Check your inbox for the verification code.',
    })
    // Automatically open verification dialog
    setVerifyingContact(result)
    setVerifyingType('email')
    setVerifyDialogOpen(true)

    // Auto-send verification code
    try {
      await sendVerification(result.id)
      toast.success('Verification code sent to your email')
    } catch {
      toast.error('Failed to send verification code', {
        description: 'You can resend it from the verification dialog.',
      })
    }
  }

  /**
   * Handle adding a new phone number
   */
  const handleAddPhone = async (phone: string) => {
    const result = await addPhone(phone)
    toast.success(`Phone added: ${result.phone}`, {
      description: 'Check your phone for the verification code.',
    })
    // Automatically open verification dialog
    setVerifyingContact(result)
    setVerifyingType('phone')
    setVerifyDialogOpen(true)

    // Auto-send verification code
    try {
      await sendVerification(result.id)
      toast.success('Verification code sent to your phone')
    } catch {
      toast.error('Failed to send verification code', {
        description: 'You can resend it from the verification dialog.',
      })
    }
  }

  /**
   * Handle verify button click from contact card
   */
  const handleVerify = async (id: string, type: 'email' | 'phone') => {
    const contact =
      type === 'email'
        ? contacts?.emails.find((e) => e.id === id)
        : contacts?.phones.find((p) => p.id === id)

    if (!contact) return

    setVerifyingContact(contact)
    setVerifyingType(type)
    setVerifyDialogOpen(true)

    // Send verification code
    try {
      await sendVerification(id)
      toast.success(`Verification code sent to your ${type}`)
    } catch {
      toast.error('Failed to send verification code')
    }
  }

  /**
   * Handle verification code submission
   */
  const handleVerifyCode = async (code: string) => {
    if (!verifyingContact) return

    await verifyCode(verifyingContact.id, code)
    const value = 'email' in verifyingContact ? verifyingContact.email : verifyingContact.phone
    toast.success(`${verifyingType === 'email' ? 'Email' : 'Phone'} verified!`, {
      description: value,
    })
  }

  /**
   * Handle resend verification code
   */
  const handleResendCode = async () => {
    if (!verifyingContact) return

    await sendVerification(verifyingContact.id)
    toast.success('Verification code resent')
  }

  /**
   * Handle deleting a contact
   */
  const handleDelete = async (id: string, type: 'email' | 'phone') => {
    const contact =
      type === 'email'
        ? contacts?.emails.find((e) => e.id === id)
        : contacts?.phones.find((p) => p.id === id)

    if (!contact) return

    const value = 'email' in contact ? contact.email : contact.phone

    try {
      setDeletingId(id)
      await deleteContact(id)
      toast.success(`${type === 'email' ? 'Email' : 'Phone'} removed`, {
        description: value,
      })
    } catch {
      toast.error('Failed to delete contact')
    } finally {
      setDeletingId(undefined)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Contacts</h1>
        <p className="text-muted-foreground mt-2">
          Manage your email addresses and phone numbers for receiving alerts.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Email Addresses Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Mail className="h-5 w-5" aria-hidden="true" />
                Email Addresses
              </span>
              <Button size="sm" onClick={() => setAddEmailOpen(true)}>
                <Plus className="h-4 w-4 mr-2" aria-hidden="true" />
                Add Email
              </Button>
            </CardTitle>
            <CardDescription>
              Add and verify email addresses to receive disruption alerts
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ContactList
              contacts={contacts?.emails || []}
              type="email"
              onVerify={(id) => handleVerify(id, 'email')}
              onDelete={(id) => handleDelete(id, 'email')}
              loading={loading}
              deletingId={deletingId}
            />
          </CardContent>
        </Card>

        {/* Phone Numbers Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Phone className="h-5 w-5" aria-hidden="true" />
                Phone Numbers
              </span>
              <Button size="sm" onClick={() => setAddPhoneOpen(true)}>
                <Plus className="h-4 w-4 mr-2" aria-hidden="true" />
                Add Phone
              </Button>
            </CardTitle>
            <CardDescription>
              Add and verify phone numbers to receive disruption alerts
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ContactList
              contacts={contacts?.phones || []}
              type="phone"
              onVerify={(id) => handleVerify(id, 'phone')}
              onDelete={(id) => handleDelete(id, 'phone')}
              loading={loading}
              deletingId={deletingId}
            />
          </CardContent>
        </Card>
      </div>

      {/* Add Email Dialog */}
      <AddContactDialog
        open={addEmailOpen}
        onClose={() => setAddEmailOpen(false)}
        type="email"
        onAdd={handleAddEmail}
      />

      {/* Add Phone Dialog */}
      <AddContactDialog
        open={addPhoneOpen}
        onClose={() => setAddPhoneOpen(false)}
        type="phone"
        onAdd={handleAddPhone}
      />

      {/* Verification Dialog */}
      <VerificationDialog
        open={verifyDialogOpen}
        onClose={() => {
          setVerifyDialogOpen(false)
          setVerifyingContact(null)
        }}
        contact={verifyingContact}
        type={verifyingType}
        onVerify={handleVerifyCode}
        onResend={handleResendCode}
        canResend={verifyingContact ? canResendVerification(verifyingContact.id) : false}
      />
    </div>
  )
}
