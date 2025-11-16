import { useState, useEffect } from 'react'
import { useAdminUsers } from '@/hooks/useAdminUsers'
import { UserTable } from '@/components/admin/UserTable'
import { UserDetailDialog } from '@/components/admin/UserDetailDialog'
import { AnonymizeUserDialog } from '@/components/admin/AnonymizeUserDialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { Search, Users, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'

/**
 * Admin Users Management Page
 *
 * Provides interface for:
 * - Viewing paginated list of all users
 * - Searching users by email/phone/external_id
 * - Filtering to include deleted users
 * - Viewing detailed user information
 * - Anonymizing users (GDPR-compliant deletion)
 *
 * Integrates useAdminUsers hook with UserTable, UserDetailDialog,
 * and AnonymizeUserDialog components.
 */
export default function AdminUsers() {
  const {
    users,
    loading,
    error,
    currentPage,
    pageSize,
    totalUsers,
    totalPages,
    searchQuery,
    includeDeleted,
    setPage,
    setSearchQuery,
    setIncludeDeleted,
    getUserDetails,
    anonymizeUser,
  } = useAdminUsers()

  // Dialog state
  const [detailUserId, setDetailUserId] = useState<string | null>(null)
  const [anonymizeUserId, setAnonymizeUserId] = useState<string | null>(null)
  const [anonymizing, setAnonymizing] = useState(false)

  // Local search state for debouncing
  const [searchInput, setSearchInput] = useState(searchQuery)

  const handleViewDetails = (userId: string) => {
    setDetailUserId(userId)
  }

  const handleOpenAnonymizeDialog = (userId: string) => {
    setAnonymizeUserId(userId)
  }

  const handleConfirmAnonymize = async (userId: string) => {
    setAnonymizing(true)
    try {
      const result = await anonymizeUser(userId)
      toast.success(result.message)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to anonymize user')
    } finally {
      setAnonymizing(false)
    }
  }

  // Debounce search input (300ms delay)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setSearchQuery(searchInput)
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [searchInput, setSearchQuery])

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: number[] = []
    const maxPagesToShow = 5

    if (totalPages <= maxPagesToShow) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Always show first page
      pages.push(1)

      // Calculate range around current page
      let start = Math.max(2, currentPage - 1)
      let end = Math.min(totalPages - 1, currentPage + 1)

      // Adjust range if at edges
      if (currentPage <= 2) {
        end = 4
      } else if (currentPage >= totalPages - 1) {
        start = totalPages - 3
      }

      // Add ellipsis if needed
      if (start > 2) {
        pages.push(-1) // -1 represents ellipsis
      }

      // Add middle pages
      for (let i = start; i <= end; i++) {
        pages.push(i)
      }

      // Add ellipsis if needed
      if (end < totalPages - 1) {
        pages.push(-2) // -2 represents ellipsis
      }

      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages)
      }
    }

    return pages
  }

  return (
    <div className="container mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Users className="h-8 w-8" />
          User Management
        </h1>
        <p className="text-muted-foreground mt-2">View and manage all users in the system</p>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1">
          <Label htmlFor="search" className="sr-only">
            Search users
          </Label>
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              id="search"
              placeholder="Search by email, phone, or external ID..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="include-deleted"
            checked={includeDeleted}
            onChange={(e) => setIncludeDeleted(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          <Label htmlFor="include-deleted" className="cursor-pointer">
            Include Deleted Users
          </Label>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error.statusText || 'An error occurred while loading users'}
          </AlertDescription>
        </Alert>
      )}

      {/* User Count */}
      {!loading && users && (
        <div className="text-sm text-muted-foreground">
          {(() => {
            const start = (currentPage - 1) * pageSize + 1
            const end = Math.min(currentPage * pageSize, totalUsers)
            return totalUsers > 0
              ? `Showing ${start}-${end} of ${totalUsers} users (Page ${currentPage} of ${totalPages})`
              : 'No users found'
          })()}
        </div>
      )}

      {/* User Table */}
      <UserTable
        users={users?.users || []}
        loading={loading}
        onViewDetails={handleViewDetails}
        onAnonymize={handleOpenAnonymizeDialog}
      />

      {/* Pagination */}
      {!loading && users && totalPages > 1 && (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                onClick={() => currentPage > 1 && setPage(currentPage - 1)}
                className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
              />
            </PaginationItem>

            {getPageNumbers().map((pageNum, index) => {
              if (pageNum < 0) {
                // Ellipsis
                return (
                  <PaginationItem key={`ellipsis-${index}`}>
                    <span className="px-3 text-muted-foreground">...</span>
                  </PaginationItem>
                )
              }

              return (
                <PaginationItem key={pageNum}>
                  <PaginationLink
                    onClick={() => setPage(pageNum)}
                    isActive={pageNum === currentPage}
                    className="cursor-pointer"
                  >
                    {pageNum}
                  </PaginationLink>
                </PaginationItem>
              )
            })}

            <PaginationItem>
              <PaginationNext
                onClick={() => currentPage < totalPages && setPage(currentPage + 1)}
                className={
                  currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'
                }
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      )}

      {/* User Detail Dialog */}
      <UserDetailDialog
        userId={detailUserId}
        open={detailUserId !== null}
        onOpenChange={(open) => !open && setDetailUserId(null)}
        onAnonymize={handleOpenAnonymizeDialog}
        fetchUserDetails={getUserDetails}
      />

      {/* Anonymize Confirmation Dialog */}
      <AnonymizeUserDialog
        userId={anonymizeUserId}
        open={anonymizeUserId !== null}
        onOpenChange={(open) => !open && setAnonymizeUserId(null)}
        onConfirm={handleConfirmAnonymize}
        loading={anonymizing}
      />
    </div>
  )
}
