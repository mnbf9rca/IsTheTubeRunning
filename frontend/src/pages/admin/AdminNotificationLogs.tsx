import { useState } from 'react'
import { Bell } from 'lucide-react'
import { useNotificationLogs } from '@/hooks/useNotificationLogs'
import { NotificationLogsTable } from '@/components/admin/NotificationLogsTable'
import { UserDetailDialog } from '@/components/admin/UserDetailDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { getAdminUser as apiGetAdminUser } from '@/lib/api'

/**
 * AdminNotificationLogs page component
 *
 * Displays notification delivery logs with:
 * - Status filter (All/Sent/Failed/Pending)
 * - Page size selector (25/50/100)
 * - Paginated logs table with expandable rows
 * - User details dialog integration
 *
 * Route: /admin/logs
 * Requires: Admin role
 */
export default function AdminNotificationLogs() {
  const {
    logs,
    loading,
    error,
    currentPage,
    pageSize,
    totalLogs,
    totalPages,
    statusFilter,
    setPage,
    setPageSize,
    setStatusFilter,
  } = useNotificationLogs()

  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)

  // Calculate current range for display
  const startIndex = totalLogs === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endIndex = Math.min(currentPage * pageSize, totalLogs)

  /**
   * Generate page numbers with ellipsis for pagination
   */
  const generatePageNumbers = (): (number | 'ellipsis')[] => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }

    const pages: (number | 'ellipsis')[] = [1]

    if (currentPage > 3) {
      pages.push('ellipsis')
    }

    const start = Math.max(2, currentPage - 1)
    const end = Math.min(totalPages - 1, currentPage + 1)

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }

    if (currentPage < totalPages - 2) {
      pages.push('ellipsis')
    }

    if (totalPages > 1) {
      pages.push(totalPages)
    }

    return pages
  }

  const pageNumbers = generatePageNumbers()

  return (
    <div className="container mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <Bell className="h-6 w-6" />
          <h1 className="text-3xl font-bold">Notification Logs</h1>
        </div>
        <p className="text-muted-foreground mt-1">
          View notification delivery logs and troubleshoot issues
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <Label htmlFor="status-filter">Filter by Status</Label>
          <Select
            value={statusFilter}
            onValueChange={(value) =>
              setStatusFilter(value as 'all' | 'sent' | 'failed' | 'pending')
            }
          >
            <SelectTrigger id="status-filter" className="w-full sm:w-[200px]">
              <SelectValue placeholder="Select status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="sent">Sent</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="page-size">Page Size</Label>
          <Select value={pageSize.toString()} onValueChange={(value) => setPageSize(Number(value))}>
            <SelectTrigger id="page-size" className="w-full sm:w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>
            Error loading logs: {error.message || 'Unknown error'}
          </AlertDescription>
        </Alert>
      )}

      {/* Log Count */}
      {!loading && logs && (
        <div className="text-sm text-muted-foreground">
          {totalLogs === 0 ? (
            'No logs found'
          ) : (
            <>
              Showing {startIndex}-{endIndex} of {totalLogs} logs
              {totalPages > 1 && ` (Page ${currentPage} of ${totalPages})`}
            </>
          )}
        </div>
      )}

      {/* Table */}
      <NotificationLogsTable
        logs={logs?.logs || []}
        loading={loading}
        onViewUser={(userId) => setSelectedUserId(userId)}
      />

      {/* Pagination */}
      {!loading && logs && totalPages > 1 && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  setPage(currentPage - 1)
                }}
                className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
              />
            </PaginationItem>

            {pageNumbers.map((pageNum, index) =>
              pageNum === 'ellipsis' ? (
                <PaginationItem key={`ellipsis-${index}`}>
                  <span className="px-4">...</span>
                </PaginationItem>
              ) : (
                <PaginationItem key={pageNum}>
                  <PaginationLink
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      setPage(pageNum)
                    }}
                    isActive={currentPage === pageNum}
                    className="cursor-pointer"
                  >
                    {pageNum}
                  </PaginationLink>
                </PaginationItem>
              )
            )}

            <PaginationItem>
              <PaginationNext
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  setPage(currentPage + 1)
                }}
                className={
                  currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'
                }
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}

      {/* User Details Dialog */}
      <UserDetailDialog
        userId={selectedUserId}
        open={selectedUserId !== null}
        onOpenChange={(open) => !open && setSelectedUserId(null)}
        onAnonymize={() => {}} // Read-only for logs view
        fetchUserDetails={apiGetAdminUser}
      />
    </div>
  )
}
