import { useState, useEffect, useCallback } from 'react'
import type { DisruptionResponse } from '@/types'
import { ApiError, getDisruptions as apiGetDisruptions } from '../lib/api'

export interface UseDisruptionsOptions {
  /** Polling interval in milliseconds (default: 30000 = 30 seconds) */
  pollInterval?: number
  /** Whether polling is enabled (default: true) */
  enabled?: boolean
  /** Filter out "Good Service" disruptions (severity 10) (default: true) */
  filterGoodService?: boolean
}

export interface UseDisruptionsReturn {
  disruptions: DisruptionResponse[] | null
  loading: boolean
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
 * - Re-check on window focus
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

  const [disruptions, setDisruptions] = useState<DisruptionResponse[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await apiGetDisruptions()

      // Filter out "Good Service" if requested
      const filteredData = filterGoodService
        ? data.filter((disruption) => disruption.status_severity !== 10)
        : data

      setDisruptions(filteredData)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [filterGoodService])

  // Initial fetch on mount
  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }

    refresh().catch(() => {
      // Error already set in state
    })
  }, [enabled, refresh])

  // Periodic polling
  useEffect(() => {
    if (!enabled) return

    const interval = setInterval(refresh, pollInterval)
    return () => clearInterval(interval)
  }, [enabled, pollInterval, refresh])

  // Re-check when window regains focus
  useEffect(() => {
    if (!enabled) return

    const handleFocus = () => {
      refresh().catch(() => {
        // Error already set in state
      })
    }

    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [enabled, refresh])

  return {
    disruptions,
    loading,
    error,
    refresh,
  }
}
