import { useState, useEffect, useCallback } from 'react'
import type {
  RouteListItemResponse,
  RouteResponse,
  CreateRouteRequest,
  UpdateRouteRequest,
} from '@/types'
import {
  ApiError,
  getRoutes as apiGetRoutes,
  getRoute as apiGetRoute,
  createRoute as apiCreateRoute,
  updateRoute as apiUpdateRoute,
  deleteRoute as apiDeleteRoute,
} from '../lib/api'

export interface UseRoutesReturn {
  // State
  routes: RouteListItemResponse[] | null
  loading: boolean
  error: ApiError | null

  // Actions
  createRoute: (data: CreateRouteRequest) => Promise<RouteResponse>
  updateRoute: (routeId: string, data: UpdateRouteRequest) => Promise<RouteResponse>
  deleteRoute: (routeId: string) => Promise<void>
  getRoute: (routeId: string) => Promise<RouteResponse>
  refresh: () => Promise<void>
}

/**
 * Hook for managing routes
 *
 * This hook provides state management and API interactions for route management.
 * It automatically fetches routes on mount and provides methods for CRUD operations.
 *
 * @returns UseRoutesReturn object with state and action methods
 *
 * @example
 * const { routes, loading, createRoute, updateRoute, deleteRoute } = useRoutes()
 *
 * // Create route
 * const route = await createRoute({ name: 'Home to Work', active: true })
 *
 * // Update route
 * await updateRoute(route.id, { active: false })
 *
 * // Delete route
 * await deleteRoute(route.id)
 */
export function useRoutes(): UseRoutesReturn {
  const [routes, setRoutes] = useState<RouteListItemResponse[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  /**
   * Fetch routes from API
   */
  const refresh = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await apiGetRoutes()
      setRoutes(data)
    } catch (err) {
      setError(err as ApiError)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  /**
   * Initial fetch on mount
   */
  useEffect(() => {
    refresh().catch(() => {
      // Error already set in state
    })
  }, [refresh])

  /**
   * Create a new route
   */
  const createRoute = useCallback(
    async (data: CreateRouteRequest): Promise<RouteResponse> => {
      try {
        setError(null)
        const newRoute = await apiCreateRoute(data)
        // Refresh to get updated list
        await refresh()
        return newRoute
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Update an existing route
   */
  const updateRoute = useCallback(
    async (routeId: string, data: UpdateRouteRequest): Promise<RouteResponse> => {
      try {
        setError(null)
        const updatedRoute = await apiUpdateRoute(routeId, data)
        // Refresh to get updated list
        await refresh()
        return updatedRoute
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Delete a route
   */
  const deleteRoute = useCallback(
    async (routeId: string): Promise<void> => {
      try {
        setError(null)
        await apiDeleteRoute(routeId)
        // Refresh to get updated list
        await refresh()
      } catch (err) {
        setError(err as ApiError)
        throw err
      }
    },
    [refresh]
  )

  /**
   * Get a single route with full details
   */
  const getRoute = useCallback(async (routeId: string): Promise<RouteResponse> => {
    try {
      setError(null)
      return await apiGetRoute(routeId)
    } catch (err) {
      setError(err as ApiError)
      throw err
    }
  }, [])

  return {
    routes,
    loading,
    error,
    createRoute,
    updateRoute,
    deleteRoute,
    getRoute,
    refresh,
  }
}
