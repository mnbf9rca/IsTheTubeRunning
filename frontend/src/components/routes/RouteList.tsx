import { MapPin } from 'lucide-react'
import { RouteCard } from './RouteCard'
import type { RouteListItemResponse, RouteDisruptionResponse } from '@/types'
import { getWorstDisruptionForRoute } from '@/lib/disruption-utils'

export interface RouteListProps {
  routes: RouteListItemResponse[]
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onClick?: (id: string) => void
  loading?: boolean
  deletingId?: string
  disruptions?: RouteDisruptionResponse[] | null
  disruptionsLoading?: boolean
}

/**
 * RouteList component displays a grid of route cards with empty state
 *
 * @param routes - Array of routes to display
 * @param onEdit - Callback when edit button is clicked
 * @param onDelete - Callback when delete button is clicked
 * @param onClick - Optional callback when card is clicked
 * @param loading - Loading state for the list
 * @param deletingId - ID of route currently being deleted
 * @param disruptions - Optional array of route disruptions
 * @param disruptionsLoading - Whether disruption data is loading
 */
export function RouteList({
  routes,
  onEdit,
  onDelete,
  onClick,
  loading = false,
  deletingId,
  disruptions,
  disruptionsLoading = false,
}: RouteListProps) {
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-48 rounded-lg border bg-card animate-pulse"
            aria-label="Loading routes"
          />
        ))}
      </div>
    )
  }

  if (routes.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-12 text-center">
        <MapPin className="mx-auto h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h3 className="mt-4 text-lg font-semibold">No routes created yet</h3>
        <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
          Create your first route to start receiving disruption alerts for your commute.
        </p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {routes.map((route) => {
        const disruption = getWorstDisruptionForRoute(disruptions, route.id) ?? null
        return (
          <RouteCard
            key={route.id}
            route={route}
            onEdit={onEdit}
            onDelete={onDelete}
            onClick={onClick}
            isDeleting={deletingId === route.id}
            disruption={disruption}
            disruptionsLoading={disruptionsLoading}
          />
        )
      })}
    </div>
  )
}
