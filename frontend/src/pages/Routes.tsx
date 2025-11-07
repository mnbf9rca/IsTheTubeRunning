import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, AlertCircle, X } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog'
import { RouteList } from '../components/routes/RouteList'
import { useRoutes } from '../hooks/useRoutes'

/**
 * Routes page for managing commute routes
 *
 * Allows users to:
 * - Create new routes
 * - Edit existing routes
 * - Delete routes
 * - View route details (segments and schedules added in PR3b)
 */
export function Routes() {
  const navigate = useNavigate()
  const { routes, loading, error, deleteRoute } = useRoutes()

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingRoute, setDeletingRoute] = useState<{ id: string; name: string } | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | undefined>()

  /**
   * Handle editing a route - navigate to route details page
   */
  const handleEdit = (routeId: string) => {
    navigate(`/routes/${routeId}`)
  }

  /**
   * Handle route card click
   */
  const handleRouteClick = (id: string) => {
    navigate(`/routes/${id}`)
  }

  /**
   * Handle delete button click
   */
  const handleDeleteClick = (id: string) => {
    const route = routes?.find((r) => r.id === id)
    if (route) {
      setDeletingRoute({ id: route.id, name: route.name })
      setDeleteDialogOpen(true)
    }
  }

  /**
   * Handle confirming deletion
   */
  const handleDeleteConfirm = async () => {
    if (!deletingRoute) return

    try {
      setIsDeleting(true)
      setDeletingId(deletingRoute.id)
      await deleteRoute(deletingRoute.id)
      toast.success('Route deleted', {
        description: `${deletingRoute.name} has been removed.`,
      })
      setDeleteDialogOpen(false)
      setDeletingRoute(null)
    } catch {
      toast.error('Failed to delete route')
    } finally {
      setIsDeleting(false)
      setDeletingId(undefined)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Routes</h1>
          <p className="text-muted-foreground mt-1">
            Manage your commute routes and receive disruption alerts
          </p>
        </div>
        <Button onClick={() => navigate('/routes/new')} disabled={loading}>
          <Plus className="h-4 w-4 mr-2" aria-hidden="true" />
          Create Route
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription className="flex items-center justify-between">
            <span>
              {error.status === 401
                ? 'Your session has expired. Please log in again.'
                : 'Failed to load routes. Please try again.'}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => window.location.reload()}
              className="ml-2"
            >
              <X className="h-4 w-4" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Your Routes</CardTitle>
          <CardDescription>
            {loading
              ? 'Loading routes...'
              : routes
                ? `You have ${routes.length} route${routes.length !== 1 ? 's' : ''}`
                : 'No routes yet'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RouteList
            routes={routes || []}
            onClick={handleRouteClick}
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
            loading={loading}
            deletingId={deletingId}
          />
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Route?</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{deletingRoute?.name}&quot;? This will also
              delete all segments, schedules, and notification preferences. This action cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm} disabled={isDeleting}>
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
