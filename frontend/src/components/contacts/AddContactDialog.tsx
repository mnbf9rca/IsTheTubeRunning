import { useState } from 'react'
import { Mail, Phone } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Alert, AlertDescription } from '../ui/alert'

export interface AddContactDialogProps {
  open: boolean
  onClose: () => void
  type: 'email' | 'phone'
  onAdd: (value: string) => Promise<void>
}

/**
 * AddContactDialog component for adding new email or phone contact
 *
 * @param open - Whether the dialog is open
 * @param onClose - Callback when dialog should close
 * @param type - Type of contact to add ('email' or 'phone')
 * @param onAdd - Async callback to add the contact (throws on error)
 */
export function AddContactDialog({ open, onClose, type, onAdd }: AddContactDialogProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isEmail = type === 'email'
  const Icon = isEmail ? Mail : Phone
  const displayName = isEmail ? 'Email Address' : 'Phone Number'
  const placeholder = isEmail ? 'you@example.com' : '+44 20 1234 5678 (E.164 format)'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Basic client-side validation
    if (!value.trim()) {
      setError(`Please enter ${isEmail ? 'an email address' : 'a phone number'}`)
      return
    }

    if (isEmail && !value.includes('@')) {
      setError('Please enter a valid email address')
      return
    }

    if (!isEmail && !value.startsWith('+')) {
      setError('Please enter phone in E.164 format (e.g., +44 20 1234 5678)')
      return
    }

    try {
      setIsSubmitting(true)
      await onAdd(value.trim())
      // Success - close dialog and reset
      handleClose()
    } catch (err) {
      // Handle API errors
      if (err && typeof err === 'object' && 'status' in err) {
        const apiError = err as { status: number; data?: { detail?: string } }
        if (apiError.status === 409) {
          setError(`This ${type} is already registered to your account.`)
        } else if (apiError.status === 429) {
          setError('Too many failed attempts. Please try again in 24 hours.')
        } else if (apiError.status === 400) {
          const detail = apiError.data?.detail || 'Invalid format'
          setError(detail)
        } else {
          setError('An error occurred. Please try again.')
        }
      } else {
        setError('An error occurred. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    setValue('')
    setError(null)
    onClose()
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      handleClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5" aria-hidden="true" />
            Add {displayName}
          </DialogTitle>
          <DialogDescription>
            Enter your {type} to add it to your account. You'll need to verify it before you can use
            it for alerts.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor={`add-${type}`}>{displayName}</Label>
              <Input
                id={`add-${type}`}
                type={isEmail ? 'email' : 'tel'}
                placeholder={placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                disabled={isSubmitting}
                autoFocus
                aria-describedby={error ? `${type}-error` : undefined}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription id={`${type}-error`}>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Adding...' : 'Add'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
