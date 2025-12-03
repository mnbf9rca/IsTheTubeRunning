import { useState, useCallback, useEffect, useRef } from 'react'
import { usePollingCoordinator } from '@/contexts/PollingContext'

export interface UsePollingOptions<T> {
  /** Unique key to identify this poll */
  key: string
  /** Async function to fetch data */
  fetchFn: () => Promise<T>
  /** Poll interval in milliseconds (default: 30000 = 30 seconds) */
  interval?: number
  /** Whether polling is enabled (default: true) */
  enabled?: boolean
  /** Whether this poll requires authentication (default: false) */
  requiresAuth?: boolean
  /** Whether to pause when backend is unavailable (default: true) */
  pauseWhenBackendDown?: boolean
  /** Optional data transformation function */
  transform?: (data: T) => T
}

export interface UsePollingReturn<T> {
  /** The fetched data */
  data: T | null
  /** True only during initial load */
  loading: boolean
  /** True during background refresh (fixes UI flicker) */
  isRefreshing: boolean
  /** Error if fetch failed */
  error: Error | null
  /** Manually trigger a refresh */
  refresh: () => Promise<void>
  /** Timestamp of last successful fetch */
  lastUpdated: Date | null
}

const DEFAULT_POLL_INTERVAL = 30000 // 30 seconds

/**
 * Generic polling hook that integrates with PollingCoordinator
 *
 * Features:
 * - Automatic polling with configurable interval
 * - Coordinated with other polls (staggered, auth-aware, health-aware)
 * - Separate loading and refreshing states to prevent UI flicker
 * - Manual refresh capability
 * - Optional data transformation
 * - Enable/disable polling
 *
 * @param options Polling configuration
 * @returns Data, loading states, error, and refresh function
 *
 * @example
 * ```ts
 * const { data, loading, isRefreshing, error, refresh } = usePolling({
 *   key: 'my-data',
 *   fetchFn: () => api.getData(),
 *   interval: 30000,
 *   requiresAuth: true,
 * })
 * ```
 */
export function usePolling<T>(options: UsePollingOptions<T>): UsePollingReturn<T> {
  const {
    key,
    fetchFn,
    interval = DEFAULT_POLL_INTERVAL,
    enabled = true,
    requiresAuth = false,
    pauseWhenBackendDown = true,
    transform,
  } = options

  const { registerPoll } = usePollingCoordinator()

  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  // Track if this is the first fetch
  const isInitialFetch = useRef(true)

  /**
   * Fetch data and update state
   */
  const fetchData = useCallback(async () => {
    // Determine if this is initial load or background refresh
    const isInitial = isInitialFetch.current

    if (isInitial) {
      setLoading(true)
    } else {
      setIsRefreshing(true)
    }

    setError(null)

    try {
      const fetchedData = await fetchFn()

      // Apply transformation if provided
      const result = transform ? transform(fetchedData) : fetchedData

      setData(result)
      setLastUpdated(new Date())
      isInitialFetch.current = false
    } catch (err) {
      setError(err as Error)
    } finally {
      if (isInitial) {
        setLoading(false)
      } else {
        setIsRefreshing(false)
      }
    }
  }, [fetchFn, transform])

  /**
   * Manual refresh function
   */
  const refresh = useCallback(async () => {
    await fetchData()
  }, [fetchData])

  // Register with polling coordinator
  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }

    // Register poll with coordinator
    const cleanup = registerPoll({
      key,
      callback: fetchData,
      interval,
      requiresAuth,
      pauseWhenBackendDown,
    })

    // Cleanup on unmount or when deps change
    return cleanup
  }, [key, fetchData, interval, enabled, requiresAuth, pauseWhenBackendDown, registerPoll])

  return {
    data,
    loading,
    isRefreshing,
    error,
    refresh,
    lastUpdated,
  }
}
