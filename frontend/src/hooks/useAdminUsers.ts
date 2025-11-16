import { useState, useEffect, useCallback } from 'react'
import {
  type PaginatedUsersResponse,
  type UserDetailResponse,
  type AnonymiseUserResponse,
  ApiError,
  getAdminUsers as apiGetAdminUsers,
  getAdminUser as apiGetAdminUser,
  anonymizeUser as apiAnonymizeUser,
} from '../lib/api'

export interface UseAdminUsersReturn {
  // State
  users: PaginatedUsersResponse | null
  loading: boolean
  error: ApiError | null

  // Pagination
  currentPage: number
  pageSize: number
  totalUsers: number
  totalPages: number

  // Filters
  searchQuery: string
  includeDeleted: boolean

  // Actions
  fetchUsers: () => Promise<void>
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  setSearchQuery: (query: string) => void
  setIncludeDeleted: (include: boolean) => void
  getUserDetails: (userId: string) => Promise<UserDetailResponse>
  anonymizeUser: (userId: string) => Promise<AnonymiseUserResponse>
  refresh: () => Promise<void>
}

/**
 * Hook for managing admin user list with search, pagination, and filters
 *
 * This hook provides state management and API interactions for admin user management.
 * It includes search, pagination controls, and user anonymization.
 *
 * @returns UseAdminUsersReturn object with state and action methods
 *
 * @example
 * const { users, loading, searchQuery, setSearchQuery, getUserDetails, anonymizeUser } = useAdminUsers()
 *
 * // Search users
 * setSearchQuery('user@example.com')
 *
 * // Get user details
 * const details = await getUserDetails('user-id')
 *
 * // Anonymize user
 * await anonymizeUser('user-id')
 */
export function useAdminUsers(): UseAdminUsersReturn {
  const [users, setUsers] = useState<PaginatedUsersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [includeDeleted, setIncludeDeleted] = useState(false)

  /**
   * Calculate total pages based on total users and page size
   * If there are zero users, totalPages is 0.
   */
  const totalUsers = users?.total ?? 0
  const totalPages = totalUsers === 0 ? 0 : Math.ceil(totalUsers / pageSize)

  /**
   * Fetch users from API with current filters and pagination
   */
  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const offset = (currentPage - 1) * pageSize

      const data = await apiGetAdminUsers({
        limit: pageSize,
        offset,
        search: searchQuery || undefined,
        include_deleted: includeDeleted ? true : undefined,
      })

      setUsers(data)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [currentPage, pageSize, searchQuery, includeDeleted])

  /**
   * Refresh - alias for fetchUsers for consistency with other hooks
   */
  const refresh = useCallback(async () => {
    await fetchUsers()
  }, [fetchUsers])

  /**
   * Set current page and trigger fetch
   */
  const setPage = useCallback((page: number) => {
    setCurrentPage(page)
  }, [])

  /**
   * Set page size and reset to page 1
   */
  const handleSetPageSize = useCallback((size: number) => {
    setPageSize(size)
    setCurrentPage(1) // Reset to first page when changing page size
  }, [])

  /**
   * Set search query and reset to page 1
   *
   * Resets to page 1 when search query changes. The fetch will be triggered
   * by the useEffect that watches searchQuery changes.
   */
  const handleSetSearchQuery = useCallback((query: string) => {
    setSearchQuery(query)
    setCurrentPage(1) // Reset to first page when search changes
  }, [])

  /**
   * Set include deleted filter and reset to page 1
   */
  const handleSetIncludeDeleted = useCallback((include: boolean) => {
    setIncludeDeleted(include)
    setCurrentPage(1) // Reset to first page when filter changes
  }, [])

  /**
   * Get detailed information for a specific user
   *
   * This does not modify the users list state - it's a standalone fetch
   * for viewing user details in a modal/dialog.
   */
  const getUserDetails = useCallback(async (userId: string): Promise<UserDetailResponse> => {
    return await apiGetAdminUser(userId)
  }, [])

  /**
   * Anonymize a user (GDPR-compliant deletion)
   *
   * After successful anonymization, refreshes the user list to show updated state.
   */
  const anonymizeUserAction = useCallback(
    async (userId: string): Promise<AnonymiseUserResponse> => {
      try {
        setError(null)
        const result = await apiAnonymizeUser(userId)

        // Refresh list to show updated user status
        await refresh()

        return result
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Initial fetch on mount
   */
  useEffect(() => {
    fetchUsers().catch(() => {
      // Error already set in state
    })
  }, [fetchUsers])

  return {
    // State
    users,
    loading,
    error,

    // Pagination
    currentPage,
    pageSize,
    totalUsers,
    totalPages,

    // Filters
    searchQuery,
    includeDeleted,

    // Actions
    fetchUsers,
    setPage,
    setPageSize: handleSetPageSize,
    setSearchQuery: handleSetSearchQuery,
    setIncludeDeleted: handleSetIncludeDeleted,
    getUserDetails,
    anonymizeUser: anonymizeUserAction,
    refresh,
  }
}
