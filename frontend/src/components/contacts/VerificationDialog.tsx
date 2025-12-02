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
import type { Contact } from '@/types'

export interface VerificationDialogProps {
  open: boolean
  onClose: () => void
  contact: Contact | null
  type: 'email' | 'phone'
  onVerify: (code: string) => Promise<void>
  onResend: () => Promise<void>
  canResend: boolean
}

/**
 * VerificationDialog component for entering and verifying a 6-digit code
 *
 * @param open - Whether the dialog is open
 * @param onClose - Callback when dialog should close
 * @param contact - The contact being verified
 * @param type - Type of contact ('email' or 'phone')
 * @param onVerify - Async callback to verify the code
 * @param onResend - Async callback to resend the code
 * @param canResend - Whether resend is allowed (client-side hint)
 */
export function VerificationDialog({
  open,
  onClose,
  contact,
  type,
  onVerify,
  onResend,
  canResend,
}: VerificationDialogProps) {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isVerifying, setIsVerifying] = useState(false)
  const [isResending, setIsResending] = useState(false)

  const isEmail = type === 'email'
  const Icon = isEmail ? Mail : Phone
  const displayName = isEmail ? 'Email' : 'Phone'
  const contactValue = contact ? ('email' in contact ? contact.email : contact.phone) : ''

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!code.trim()) {
      setError('Please enter the verification code')
      return
    }

    if (code.length !== 6) {
      setError('Verification code must be 6 digits')
      return
    }

    if (!/^\d{6}$/.test(code)) {
      setError('Verification code must contain only numbers')
      return
    }

    try {
      setIsVerifying(true)
      await onVerify(code.trim())
      // Success - close dialog and reset
      handleClose()
    } catch (err) {
      // Handle API errors
      if (err && typeof err === 'object' && 'status' in err) {
        const apiError = err as { status: number; data?: { detail?: string } }
        const detail = apiError.data?.detail

        if (apiError.status === 400) {
          if (detail?.includes('expired')) {
            setError('Verification code has expired. Please request a new one.')
          } else {
            setError('Invalid verification code. Please try again.')
          }
        } else if (apiError.status === 404) {
          setError('Contact not found. Please close and try again.')
        } else {
          setError('An error occurred. Please try again.')
        }
      } else {
        setError('An error occurred. Please try again.')
      }
    } finally {
      setIsVerifying(false)
    }
  }

  const handleResend = async () => {
    setError(null)
    try {
      setIsResending(true)
      await onResend()
      setCode('') // Clear code input after resend
    } catch (err) {
      // Handle API errors
      if (err && typeof err === 'object' && 'status' in err) {
        const apiError = err as { status: number; data?: { detail?: string } }
        if (apiError.status === 429) {
          setError('Too many resend attempts. Please wait before trying again.')
        } else if (apiError.status === 404) {
          setError('Contact not found. Please close and try again.')
        } else {
          setError('Failed to resend code. Please try again.')
        }
      } else {
        setError('Failed to resend code. Please try again.')
      }
    } finally {
      setIsResending(false)
    }
  }

  const handleClose = () => {
    setCode('')
    setError(null)
    onClose()
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isVerifying && !isResending) {
      handleClose()
    }
  }

  const handleCodeChange = (value: string) => {
    // Only allow digits and limit to 6 characters
    const cleaned = value.replace(/\D/g, '').slice(0, 6)
    setCode(cleaned)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="h-5 w-5" aria-hidden="true" />
            Verify {displayName}
          </DialogTitle>
          <DialogDescription>
            We've sent a 6-digit verification code to{' '}
            <span className="font-medium text-foreground">{contactValue}</span>. Enter it below to
            verify.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleVerify}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="verification-code">Verification Code</Label>
              <Input
                id="verification-code"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                placeholder="123456"
                value={code}
                onChange={(e) => handleCodeChange(e.target.value)}
                disabled={isVerifying || isResending}
                autoFocus
                maxLength={6}
                className="text-center text-lg tracking-widest"
                aria-describedby={error ? 'verification-error' : 'code-hint'}
              />
              <p id="code-hint" className="text-xs text-muted-foreground">
                Code expires in 15 minutes
              </p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription id="verification-error">{error}</AlertDescription>
              </Alert>
            )}

            {!canResend && (
              <Alert>
                <AlertDescription>
                  Maximum resend attempts reached (3 per hour). Please wait before requesting
                  another code.
                </AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-between">
            <Button
              type="button"
              variant="ghost"
              onClick={handleResend}
              disabled={!canResend || isVerifying || isResending}
              className="w-full sm:w-auto"
            >
              {isResending ? 'Sending...' : 'Resend Code'}
            </Button>
            <div className="flex gap-2 w-full sm:w-auto">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isVerifying || isResending}
                className="flex-1 sm:flex-none"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isVerifying || isResending || code.length !== 6}
                className="flex-1 sm:flex-none"
              >
                {isVerifying ? 'Verifying...' : 'Verify'}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
