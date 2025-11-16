import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertTriangle } from 'lucide-react'

interface AnonymizeUserDialogProps {
  userId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (userId: string) => Promise<void>
  loading?: boolean
}

const CONFIRMATION_TEXT = 'ANONYMIZE'

/**
 * Dialog component for confirming user anonymization
 *
 * Requires the user to type "ANONYMIZE" to confirm the irreversible action.
 * Displays a warning message explaining what will be anonymized.
 *
 * @param userId - User ID to anonymize (null if dialog is closed)
 * @param open - Whether the dialog is open
 * @param onOpenChange - Callback when dialog open state changes
 * @param onConfirm - Callback to confirm anonymization
 * @param loading - Whether anonymization is in progress
 */
export function AnonymizeUserDialog({
  userId,
  open,
  onOpenChange,
  onConfirm,
  loading = false,
}: AnonymizeUserDialogProps) {
  const [confirmationInput, setConfirmationInput] = useState('')

  const isConfirmationValid = confirmationInput === CONFIRMATION_TEXT

  const handleConfirm = async () => {
    if (userId && isConfirmationValid) {
      await onConfirm(userId)
      // Reset state and close dialog
      setConfirmationInput('')
      onOpenChange(false)
    }
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      // Reset confirmation input when closing
      setConfirmationInput('')
    }
    onOpenChange(newOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Anonymize User
          </DialogTitle>
          <DialogDescription>
            This action is <strong>irreversible</strong> and cannot be undone.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <strong>Warning:</strong> This will permanently:
              <ul className="list-disc list-inside mt-2 space-y-1">
                <li>Remove all email addresses</li>
                <li>Remove all phone numbers</li>
                <li>Delete all verification codes</li>
                <li>Anonymize the external ID</li>
                <li>Deactivate all routes</li>
              </ul>
              <p className="mt-2">
                Analytics data will be preserved for reporting purposes, but all personally
                identifiable information (PII) will be permanently deleted.
              </p>
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <Label htmlFor="confirmation">
              Type <code className="bg-muted px-1 py-0.5 rounded">{CONFIRMATION_TEXT}</code> to
              confirm
            </Label>
            <Input
              id="confirmation"
              value={confirmationInput}
              onChange={(e) => setConfirmationInput(e.target.value)}
              placeholder={CONFIRMATION_TEXT}
              disabled={loading}
              autoComplete="off"
              className={confirmationInput && !isConfirmationValid ? 'border-destructive' : ''}
            />
            {confirmationInput && !isConfirmationValid && (
              <p className="text-sm text-destructive">
                Please type "{CONFIRMATION_TEXT}" exactly as shown
              </p>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!isConfirmationValid || loading}
          >
            {loading ? 'Anonymizing...' : 'Confirm Anonymization'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
