import { useState, useEffect, useCallback } from 'react'
import type { RouteDisruptionResponse } from '@/types'
import { ApiError, getRouteDisruptions as apiGetRouteDisruptions } from '../lib/api'

export interface UseUserRouteDisruptionsOptions {
  /** Polling interval in milliseconds (default: 30000 = 30 seconds) */
  pollInterval?: number
  /** Whether polling is enabled (default: true) */
  enabled?: boolean
  /** Filter to only active routes (default: true) */
  activeOnly?: boolean
}

export interface UseUserRouteDisruptionsReturn {
  disruptions: RouteDisruptionResponse[] | null
  loading: boolean
  error: ApiError | null
  refresh: () => Promise<void>
}

const DEFAULT_POLL_INTERVAL = 30000 // 30 seconds

/**
 * Hook for fetching and polling user-specific route disruptions
 *
 * Polls the route disruptions endpoint at a configurable interval. Returns
 * only disruptions affecting the authenticated user's routes, with route-specific
 * context (affected segments and stations).
 *
 * Supports:
 * - Automatic polling with cleanup
 * - Filter by active routes only
 * - Enable/disable polling
 * - Manual refresh
 * - Re-check on window focus
 *
 * @param options Configuration options
 * @returns Disruption data, loading state, error, and refresh function
 *
 * @example
 * const { disruptions, loading, error } = useUserRouteDisruptions({
 *   pollInterval: 30000,
 *   activeOnly: true
 * })
 */
export function useUserRouteDisruptions(
  options: UseUserRouteDisruptionsOptions = {}
): UseUserRouteDisruptionsReturn {
  const { pollInterval = DEFAULT_POLL_INTERVAL, enabled = true, activeOnly = true } = options

  const [disruptions, setDisruptions] = useState<RouteDisruptionResponse[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await apiGetRouteDisruptions(activeOnly)
      setDisruptions(data)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [activeOnly])

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
