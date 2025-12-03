import { useCallback } from 'react'
import type { GroupedLineDisruptionResponse } from '@/types'
import { ApiError, getDisruptions as apiGetDisruptions } from '../lib/api'
import { usePolling } from './usePolling'

export interface UseDisruptionsOptions {
  /** Polling interval in milliseconds (default: 30000 = 30 seconds) */
  pollInterval?: number
  /** Whether polling is enabled (default: true) */
  enabled?: boolean
  /** Filter out "Good Service" disruptions (severity 10) (default: true) */
  filterGoodService?: boolean
}

export interface UseDisruptionsReturn {
  disruptions: GroupedLineDisruptionResponse[] | null
  loading: boolean
  isRefreshing: boolean
  error: ApiError | null
  refresh: () => Promise<void>
}

const DEFAULT_POLL_INTERVAL = 30000 // 30 seconds

/**
 * Hook for fetching and polling TfL network disruptions
 *
 * Polls the TfL disruptions endpoint at a configurable interval. Supports:
 * - Automatic polling with cleanup
 * - Optional filtering of "Good Service" status
 * - Enable/disable polling
 * - Manual refresh
 * - Re-check on window focus (via PollingCoordinator)
 *
 * @param options Configuration options
 * @returns Disruption data, loading state, error, and refresh function
 *
 * @example
 * const { disruptions, loading, error } = useDisruptions({
 *   pollInterval: 30000,
 *   filterGoodService: true
 * })
 */
export function useDisruptions(options: UseDisruptionsOptions = {}): UseDisruptionsReturn {
  const { pollInterval = DEFAULT_POLL_INTERVAL, enabled = true, filterGoodService = true } = options

  // Memoize transform function to prevent unnecessary re-registrations
  // Filter out lines where ALL statuses are "Good Service" (severity 10)
  const transform = useCallback(
    (data: GroupedLineDisruptionResponse[]) =>
      data.filter((line) => line.statuses.some((status) => status.status_severity !== 10)),
    []
  )

  const {
    data: disruptions,
    loading,
    isRefreshing,
    error,
    refresh,
  } = usePolling<GroupedLineDisruptionResponse[]>({
    key: 'disruptions',
    fetchFn: apiGetDisruptions,
    interval: pollInterval,
    enabled,
    requiresAuth: false,
    pauseWhenBackendDown: true,
    transform: filterGoodService ? transform : undefined,
  })

  // Expose both loading (initial) and isRefreshing (background) states separately
  // This allows consumers to handle UI differently for initial load vs background refresh
  return {
    disruptions,
    loading,
    isRefreshing,
    error: error as ApiError | null,
    refresh,
  }
}
