import React, { useState } from 'react'
import { type NotificationLogItem } from '@/lib/api'
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
import { NotificationStatusBadge } from './NotificationStatusBadge'
import { NotificationMethodBadge } from './NotificationMethodBadge'
import { ChevronRight, ChevronDown, Copy, Eye } from 'lucide-react'
import { toast } from 'sonner'

interface NotificationLogsTableProps {
  logs: NotificationLogItem[]
  loading: boolean
  onViewUser: (userId: string) => void
}

/**
 * Truncate UUID to first 12 characters for display
 */
function truncateId(id: string): string {
  return id.substring(0, 12) + '...'
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
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    if (diffHours < 1) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60))
      return diffMinutes <= 1 ? 'Just now' : `${diffMinutes} minutes ago`
    }
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`
  } else if (diffDays === 1) {
    return 'Yesterday'
  } else if (diffDays < 7) {
    return `${diffDays} days ago`
  } else {
    return date.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
}

/**
 * Copy text to clipboard and show toast
 */
async function copyToClipboard(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(`${label} copied to clipboard`)
  } catch {
    toast.error(`Failed to copy ${label}`)
  }
}

/**
 * Table component for displaying notification logs with expandable rows
 *
 * Displays paginated list of notification logs with:
 * - Sent At (formatted timestamp)
 * - Route Name (from backend)
 * - Method (email/sms badge)
 * - Status (sent/failed/pending badge)
 * - User (truncated ID with view button)
 * - Expandable rows showing:
 *   - Route UUID (with copy button)
 *   - Full error message (if failed)
 *
 * @param logs - Array of notification log items to display
 * @param loading - Loading state (shows skeletons)
 * @param onViewUser - Callback when user details button is clicked
 */
export function NotificationLogsTable({ logs, loading, onViewUser }: NotificationLogsTableProps) {
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null)

  /**
   * Toggle row expansion
   */
  const toggleRow = (logId: string) => {
    setExpandedRowId(expandedRowId === logId ? null : logId)
  }

  // Loading state
  if (loading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10"></TableHead>
              <TableHead>Sent At</TableHead>
              <TableHead>Route</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>User</TableHead>
              <TableHead className="w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...Array(5)].map((_, i) => (
              <TableRow key={i}>
                <TableCell>
                  <Skeleton className="h-4 w-4" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-24" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-32" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-5 w-16" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-5 w-16" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-4 w-28" />
                </TableCell>
                <TableCell>
                  <Skeleton className="h-8 w-16" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    )
  }

  // Empty state
  if (logs.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center">
        <p className="text-muted-foreground">No notification logs found</p>
        <p className="text-sm text-muted-foreground mt-1">
          Logs will appear here when notifications are sent
        </p>
      </div>
    )
  }

  // Data table
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10"></TableHead>
            <TableHead>Sent At</TableHead>
            <TableHead>Route</TableHead>
            <TableHead>Method</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>User</TableHead>
            <TableHead className="w-20">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => {
            const isExpanded = expandedRowId === log.id
            return (
              <React.Fragment key={log.id}>
                {/* Main Row */}
                <TableRow
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => toggleRow(log.id)}
                >
                  <TableCell className="text-center">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 inline" />
                    ) : (
                      <ChevronRight className="h-4 w-4 inline" />
                    )}
                  </TableCell>
                  <TableCell title={new Date(log.sent_at).toLocaleString('en-GB')}>
                    {formatDate(log.sent_at)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {log.route_name || (
                      <span className="text-muted-foreground italic">Unknown</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <NotificationMethodBadge method={log.method} />
                  </TableCell>
                  <TableCell>
                    <NotificationStatusBadge status={log.status} />
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <span title={log.user_id}>{truncateId(log.user_id)}</span>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onViewUser(log.user_id)
                      }}
                      className="gap-1"
                    >
                      <Eye className="h-4 w-4" />
                      View
                    </Button>
                  </TableCell>
                </TableRow>

                {/* Expanded Row */}
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={7} className="bg-muted/30">
                      <div className="p-4 space-y-3">
                        {/* Route UUID */}
                        <div>
                          <span className="font-medium text-sm">Route UUID:</span>
                          <div className="flex items-center gap-2 mt-1">
                            <code className="text-xs bg-background px-2 py-1 rounded border font-mono">
                              {log.route_id}
                            </code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(log.route_id, 'Route ID')}
                              className="h-7"
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>

                        {/* Error Message (if failed) */}
                        {log.status === 'failed' && (
                          <div>
                            <span className="font-medium text-sm">Error Message:</span>
                            <pre className="mt-1 p-2 bg-background rounded border text-xs whitespace-pre-wrap font-mono">
                              {log.error_message || 'No error message available'}
                            </pre>
                          </div>
                        )}

                        {/* Truncated error hint (if shown in main row) */}
                        {log.status === 'failed' &&
                          log.error_message &&
                          log.error_message.length > 100 && (
                            <p className="text-xs text-muted-foreground">
                              Full error message displayed above
                            </p>
                          )}
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
