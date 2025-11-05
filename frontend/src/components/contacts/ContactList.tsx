import { Mail, Phone } from 'lucide-react'
import { ContactCard } from './ContactCard'
import type { Contact } from '../../lib/api'

export interface ContactListProps {
  contacts: Contact[]
  type: 'email' | 'phone'
  onVerify: (id: string) => void
  onDelete: (id: string) => void
  loading?: boolean
  verifyingId?: string
  deletingId?: string
}

/**
 * ContactList component displays a list of contacts with empty state
 *
 * @param contacts - Array of contacts to display
 * @param type - Type of contacts ('email' or 'phone')
 * @param onVerify - Callback when verify button is clicked
 * @param onDelete - Callback when delete button is clicked
 * @param loading - Loading state for the list
 * @param verifyingId - ID of contact currently being verified
 * @param deletingId - ID of contact currently being deleted
 */
export function ContactList({
  contacts,
  type,
  onVerify,
  onDelete,
  loading = false,
  verifyingId,
  deletingId,
}: ContactListProps) {
  const Icon = type === 'email' ? Mail : Phone
  const displayName = type === 'email' ? 'email addresses' : 'phone numbers'

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-20 rounded-lg border bg-card animate-pulse"
            aria-label="Loading contacts"
          />
        ))}
      </div>
    )
  }

  if (contacts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center">
        <Icon className="mx-auto h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h3 className="mt-4 text-sm font-semibold">No {displayName} added yet</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Add your first {type === 'email' ? 'email address' : 'phone number'} to get started.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {contacts.map((contact) => (
        <ContactCard
          key={contact.id}
          contact={contact}
          type={type}
          onVerify={onVerify}
          onDelete={onDelete}
          isVerifying={verifyingId === contact.id}
          isDeleting={deletingId === contact.id}
        />
      ))}
    </div>
  )
}
