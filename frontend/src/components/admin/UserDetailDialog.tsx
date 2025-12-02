import { useState, useEffect } from 'react'
import type { UserDetailResponse } from '@/types'
import { ApiError } from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { UserStatusBadge } from './UserStatusBadge'
import { CheckCircle, XCircle, User, Mail, Phone, Calendar } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface UserDetailDialogProps {
  userId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onAnonymize: (userId: string) => void
  fetchUserDetails: (userId: string) => Promise<UserDetailResponse>
}

/**
 * Dialog component for displaying detailed user information
 *
 * Fetches and displays:
 * - User ID, external_id, auth_provider
 * - All email addresses with verification status
 * - All phone numbers with verification status
 * - Created/updated/deleted timestamps
 *
 * Provides action to anonymize the user.
 *
 * @param userId - User ID to fetch details for (null if dialog is closed)
 * @param open - Whether the dialog is open
 * @param onOpenChange - Callback when dialog open state changes
 * @param onAnonymize - Callback to anonymize user
 * @param fetchUserDetails - Function to fetch user details
 */
export function UserDetailDialog({
  userId,
  open,
  onOpenChange,
  onAnonymize,
  fetchUserDetails,
}: UserDetailDialogProps) {
  const [userDetails, setUserDetails] = useState<UserDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  // Fetch user details when dialog opens with userId
  useEffect(() => {
    if (!open || !userId) {
      return
    }

    let cancelled = false

    const fetchData = async () => {
      if (cancelled) return

      setLoading(true)
      setError(null)

      try {
        const details = await fetchUserDetails(userId)
        if (!cancelled) {
          setUserDetails(details)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err as ApiError)
          setLoading(false)
        }
      }
    }

    fetchData()

    return () => {
      cancelled = true
    }
  }, [open, userId, fetchUserDetails])

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      // Reset state when closing
      setUserDetails(null)
      setError(null)
    }
    onOpenChange(newOpen)
  }

  const handleAnonymize = async () => {
    if (!userId) return

    try {
      await onAnonymize(userId)
      handleOpenChange(false)
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err
          : ({ statusText: 'Failed to anonymize user. Please try again.' } as ApiError)
      )
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            User Details
          </DialogTitle>
          <DialogDescription>View comprehensive information about this user</DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="space-y-4 py-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-4 w-full" />
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>
              Failed to load user details: {error.statusText || 'Unknown error'}
            </AlertDescription>
          </Alert>
        )}

        {!loading && userDetails && (
          <div className="space-y-6 py-4">
            {/* User Status */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Status:</span>
              <UserStatusBadge deletedAt={userDetails.deleted_at ?? null} />
            </div>

            {/* User ID */}
            <div>
              <h4 className="text-sm font-medium mb-2">User ID</h4>
              <code className="text-xs bg-muted p-2 rounded block font-mono">{userDetails.id}</code>
            </div>

            {/* External ID & Provider */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="text-sm font-medium mb-2">External ID</h4>
                <p className="text-sm text-muted-foreground break-all">{userDetails.external_id}</p>
              </div>
              <div>
                <h4 className="text-sm font-medium mb-2">Auth Provider</h4>
                <Badge variant="outline">{userDetails.auth_provider}</Badge>
              </div>
            </div>

            {/* Email Addresses */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Mail className="h-4 w-4" />
                Email Addresses
              </h4>
              {(userDetails.email_addresses ?? []).length > 0 ? (
                <div className="space-y-2">
                  {(userDetails.email_addresses ?? []).map((email) => (
                    <div
                      key={email.id}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{email.email}</span>
                        {email.is_primary && (
                          <Badge variant="secondary" className="text-xs">
                            Primary
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {email.verified ? (
                          <>
                            <CheckCircle className="h-4 w-4 text-green-600" />
                            <span className="text-xs text-green-600">Verified</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="h-4 w-4 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">Unverified</span>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No email addresses</p>
              )}
            </div>

            {/* Phone Numbers */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Phone className="h-4 w-4" />
                Phone Numbers
              </h4>
              {(userDetails.phone_numbers ?? []).length > 0 ? (
                <div className="space-y-2">
                  {(userDetails.phone_numbers ?? []).map((phone) => (
                    <div
                      key={phone.id}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{phone.phone}</span>
                        {phone.is_primary && (
                          <Badge variant="secondary" className="text-xs">
                            Primary
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        {phone.verified ? (
                          <>
                            <CheckCircle className="h-4 w-4 text-green-600" />
                            <span className="text-xs text-green-600">Verified</span>
                          </>
                        ) : (
                          <>
                            <XCircle className="h-4 w-4 text-muted-foreground" />
                            <span className="text-xs text-muted-foreground">Unverified</span>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No phone numbers</p>
              )}
            </div>

            {/* Timestamps */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                Timestamps
              </h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">Created:</span>
                  <span className="ml-2">{new Date(userDetails.created_at).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Updated:</span>
                  <span className="ml-2">{new Date(userDetails.updated_at).toLocaleString()}</span>
                </div>
                {userDetails.deleted_at && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Deleted:</span>
                    <span className="ml-2 text-destructive">
                      {new Date(userDetails.deleted_at).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Close
          </Button>
          {userDetails && !userDetails.deleted_at && (
            <Button variant="destructive" onClick={handleAnonymize}>
              Anonymize User
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
