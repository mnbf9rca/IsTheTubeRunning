import type { RouteDisruptionResponse } from '@/types'

/**
 * Get the worst (most severe) disruption for a specific route
 *
 * TfL severity codes: Lower numbers = more severe
 * - 1-4: Severe disruptions (closures, suspensions)
 * - 5-9: Minor/moderate delays
 * - 10: Good Service
 * - 11-20: Severe delays, reduced service
 *
 * @param disruptions - Array of route disruptions (can be null)
 * @param routeId - The route ID to filter by
 * @returns The most severe disruption for the route, or null if none exist
 *
 * @example
 * const worst = getWorstDisruptionForRoute(disruptions, 'route-123')
 * if (worst) {
 *   console.log(`Route has ${worst.disruption.status_severity_description}`)
 * }
 */
export function getWorstDisruptionForRoute(
  disruptions: RouteDisruptionResponse[] | null | undefined,
  routeId: string
): RouteDisruptionResponse | null {
  if (!disruptions || disruptions.length === 0) {
    return null
  }

  const routeDisruptions = disruptions.filter((d) => d.route_id === routeId)

  if (routeDisruptions.length === 0) {
    return null
  }

  // Return the disruption with the lowest severity number (most severe)
  return routeDisruptions.reduce((worst, current) =>
    current.disruption.status_severity < worst.disruption.status_severity ? current : worst
  )
}
