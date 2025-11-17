import { useState, useEffect, useCallback } from 'react'
import {
  type RecentLogsResponse,
  type NotificationStatus,
  ApiError,
  getRecentLogs as apiGetRecentLogs,
} from '../lib/api'

export interface UseNotificationLogsReturn {
  // State
  logs: RecentLogsResponse | null
  loading: boolean
  error: ApiError | null

  // Pagination
  currentPage: number
  pageSize: number
  totalLogs: number
  totalPages: number

  // Filters
  statusFilter: NotificationStatus | 'all'

  // Actions
  fetchLogs: () => Promise<void>
  setPage: (page: number) => void
  setPageSize: (size: number) => void
  setStatusFilter: (status: NotificationStatus | 'all') => void
  refresh: () => Promise<void>
}

/**
 * Hook for managing notification logs with pagination and filtering
 *
 * This hook provides state management and API interactions for viewing notification logs.
 * It includes pagination controls and status filtering.
 *
 * @returns UseNotificationLogsReturn object with state and action methods
 *
 * @example
 * const { logs, loading, statusFilter, setStatusFilter, setPage } = useNotificationLogs()
 *
 * // Filter by status
 * setStatusFilter('failed')
 *
 * // Change page
 * setPage(2)
 *
 * // Refresh data
 * await refresh()
 */
export function useNotificationLogs(): UseNotificationLogsReturn {
  const [logs, setLogs] = useState<RecentLogsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  // Filter state
  const [statusFilter, setStatusFilter] = useState<NotificationStatus | 'all'>('all')

  /**
   * Calculate total pages based on total logs and page size
   * If there are zero logs, totalPages is 0.
   */
  const totalLogs = logs?.total ?? 0
  const totalPages = totalLogs === 0 ? 0 : Math.ceil(totalLogs / pageSize)

  /**
   * Fetch logs from API with current filters and pagination
   */
  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const offset = (currentPage - 1) * pageSize

      const data = await apiGetRecentLogs({
        limit: pageSize,
        offset,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      })

      setLogs(data)
    } catch (err) {
      setError(err as ApiError)
      // Don't re-throw - error is captured in state for UI to handle
    } finally {
      setLoading(false)
    }
  }, [currentPage, pageSize, statusFilter])

  /**
   * Auto-fetch logs on mount and when filters/pagination change
   */
  useEffect(() => {
    void fetchLogs()
  }, [fetchLogs])

  /**
   * Set page and ensure it's within valid range
   */
  const handleSetPage = useCallback(
    (page: number) => {
      const validPage = Math.max(1, Math.min(page, totalPages || 1))
      setCurrentPage(validPage)
    },
    [totalPages]
  )

  /**
   * Set page size and reset to page 1
   */
  const handleSetPageSize = useCallback((size: number) => {
    setPageSize(size)
    setCurrentPage(1)
  }, [])

  /**
   * Set status filter and reset to page 1
   */
  const handleSetStatusFilter = useCallback((status: NotificationStatus | 'all') => {
    setStatusFilter(status)
    setCurrentPage(1)
  }, [])

  /**
   * Refresh data with current filters
   */
  const refresh = useCallback(async () => {
    return fetchLogs()
  }, [fetchLogs])

  return {
    // State
    logs,
    loading,
    error,

    // Pagination
    currentPage,
    pageSize,
    totalLogs,
    totalPages,

    // Filters
    statusFilter,

    // Actions
    fetchLogs,
    setPage: handleSetPage,
    setPageSize: handleSetPageSize,
    setStatusFilter: handleSetStatusFilter,
    refresh,
  }
}
