import { useState } from 'react'
import { type UserListItem } from '@/types'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { UserStatusBadge } from './UserStatusBadge'
import { Copy, Eye, Trash2, CheckCircle, XCircle } from 'lucide-react'
import { toast } from 'sonner'

interface UserTableProps {
  users: UserListItem[]
  loading: boolean
  onViewDetails: (userId: string) => void
  onAnonymize: (userId: string) => void
}

/**
 * Truncate UUID to first 12 characters for display (better visibility)
 */
function truncateId(id: string): string {
  return id.substring(0, 12) + '...'
}

/**
 * Truncate external ID for display (Auth0 IDs can be long)
 */
function truncateExternalId(externalId: string): string {
  if (externalId.length <= 24) {
    return externalId
  }
  return externalId.substring(0, 24) + '...'
}

/**
 * Format date to relative time or absolute date
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString)

  // Handle invalid dates
  if (isNaN(date.getTime())) {
    return 'Invalid date'
  }

  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return 'Today'
  } else if (diffDays === 1) {
    return 'Yesterday'
  } else if (diffDays < 7) {
    return `${diffDays} days ago`
  } else if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return `${weeks} ${weeks === 1 ? 'week' : 'weeks'} ago`
  } else {
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  }
}

/**
 * Table component for displaying users with actions
 *
 * Displays paginated list of users with:
 * - Internal ID (internal UUID, truncated with copy button)
 * - External ID (Auth0 user ID)
 * - Auth Provider
 * - Email addresses with verified badges
 * - Phone numbers with verified badges
 * - Created date
 * - Status badge (Active/Deleted)
 * - Actions (View Details, Anonymize)
 *
 * Shows skeleton loaders during fetch and empty state when no users found.
 */
export function UserTable({ users, loading, onViewDetails, onAnonymize }: UserTableProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const handleCopyId = async (id: string) => {
    try {
      await navigator.clipboard.writeText(id)
      setCopiedId(id)
      toast.success('User ID copied to clipboard')
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      toast.error('Failed to copy ID to clipboard')
    }
  }

  // Loading state
  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  // Empty state
  if (users.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">No users found</p>
        <p className="text-sm text-muted-foreground mt-2">Try adjusting your search or filters</p>
      </div>
    )
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[160px]">Internal ID</TableHead>
            <TableHead className="w-[240px]">External ID</TableHead>
            <TableHead className="w-[90px]">Provider</TableHead>
            <TableHead className="min-w-[200px]">Emails</TableHead>
            <TableHead className="min-w-[150px]">Phones</TableHead>
            <TableHead className="w-[120px]">Created</TableHead>
            <TableHead className="w-[90px]">Status</TableHead>
            <TableHead className="w-[220px] text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id}>
              {/* Internal UUID with copy button */}
              <TableCell className="font-mono text-xs">
                <div className="flex items-center gap-1">
                  <span title={user.id}>{truncateId(user.id)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    onClick={() => handleCopyId(user.id)}
                    title="Copy full UUID"
                  >
                    <Copy className={`h-3 w-3 ${copiedId === user.id ? 'text-green-600' : ''}`} />
                  </Button>
                </div>
              </TableCell>

              {/* External ID (Auth0 user ID) */}
              <TableCell className="font-mono text-xs">
                <span title={user.external_id}>{truncateExternalId(user.external_id)}</span>
              </TableCell>

              {/* Auth Provider */}
              <TableCell>
                <span className="text-sm">{user.auth_provider}</span>
              </TableCell>

              {/* Emails with verified badges */}
              <TableCell>
                {(user.email_addresses ?? []).length > 0 ? (
                  <div className="flex flex-col gap-1">
                    {(user.email_addresses ?? []).map((email) => (
                      <div key={email.id} className="flex items-center gap-1">
                        <span className="text-sm truncate max-w-[200px]" title={email.email}>
                          {email.email}
                        </span>
                        {email.verified ? (
                          <CheckCircle className="h-3 w-3 text-green-600 flex-shrink-0" />
                        ) : (
                          <XCircle className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">None</span>
                )}
              </TableCell>

              {/* Phones with verified badges */}
              <TableCell>
                {(user.phone_numbers ?? []).length > 0 ? (
                  <div className="flex flex-col gap-1">
                    {(user.phone_numbers ?? []).map((phone) => (
                      <div key={phone.id} className="flex items-center gap-1">
                        <span className="text-sm">{phone.phone}</span>
                        {phone.verified ? (
                          <CheckCircle className="h-3 w-3 text-green-600 flex-shrink-0" />
                        ) : (
                          <XCircle className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-sm text-muted-foreground">None</span>
                )}
              </TableCell>

              {/* Created date */}
              <TableCell>
                <span className="text-sm" title={new Date(user.created_at).toLocaleString()}>
                  {formatDate(user.created_at)}
                </span>
              </TableCell>

              {/* Status badge */}
              <TableCell>
                <UserStatusBadge deletedAt={user.deleted_at ?? null} />
              </TableCell>

              {/* Actions */}
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onViewDetails(user.id)}
                    title="View user details"
                  >
                    <Eye className="h-4 w-4 mr-1" />
                    View
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => onAnonymize(user.id)}
                    disabled={!!user.deleted_at}
                    title={user.deleted_at ? 'Already anonymized' : 'Anonymize user'}
                  >
                    <Trash2 className="h-4 w-4 mr-1" />
                    Anonymize
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
