import { useCallback } from 'react'
import type { RouteDisruptionResponse } from '@/types'
import { ApiError, getRouteDisruptions as apiGetRouteDisruptions } from '../lib/api'
import { usePolling } from './usePolling'

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
  isRefreshing: boolean
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
 * - Re-check on window focus (via PollingCoordinator)
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

  // Memoize fetchFn to prevent unnecessary re-registrations
  const fetchFn = useCallback(() => apiGetRouteDisruptions(activeOnly), [activeOnly])

  const {
    data: disruptions,
    loading,
    isRefreshing,
    error,
    refresh,
  } = usePolling<RouteDisruptionResponse[]>({
    key: 'user-route-disruptions',
    fetchFn,
    interval: pollInterval,
    enabled,
    requiresAuth: true,
    pauseWhenBackendDown: true,
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
