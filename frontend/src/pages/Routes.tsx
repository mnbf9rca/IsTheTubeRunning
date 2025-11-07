import { useState } from 'react'
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
import { RouteFormDialog, type RouteFormData } from '../components/routes/RouteFormDialog'
import { useRoutes } from '../hooks/useRoutes'
import type { RouteResponse } from '../lib/api'

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
  const { routes, loading, error, createRoute, updateRoute, deleteRoute } = useRoutes()

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [createError, setCreateError] = useState<string | undefined>(undefined)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [editingRoute, setEditingRoute] = useState<RouteResponse | undefined>()
  const [editError, setEditError] = useState<string | undefined>(undefined)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deletingRoute, setDeletingRoute] = useState<{ id: string; name: string } | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deletingId, setDeletingId] = useState<string | undefined>()

  /**
   * Handle creating a new route
   */
  const handleCreate = async (data: RouteFormData) => {
    try {
      const result = await createRoute(data)
      setCreateDialogOpen(false)
      setCreateError(undefined)
      toast.success('Route created', {
        description: `${result.name} has been created. You can now add segments and schedules.`,
      })
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create route.')
    }
  }

  /**
   * Handle editing a route
   */
  const handleEdit = async (routeId: string) => {
    try {
      // For now, we'll use a simple approach - in production you'd want to handle this better
      // Since we only edit metadata in PR3a, we can work with the list item data
      const routeFromList = routes?.find((r) => r.id === routeId)
      if (routeFromList) {
        setEditingRoute({
          ...routeFromList,
          segments: [],
          schedules: [],
        } as RouteResponse)
        setEditDialogOpen(true)
      }
    } catch {
      toast.error('Failed to load route details')
    }
  }

  /**
   * Handle submitting route edit
   */
  const handleEditSubmit = async (data: RouteFormData) => {
    if (!editingRoute) return

    try {
      const result = await updateRoute(editingRoute.id, data)
      setEditDialogOpen(false)
      setEditingRoute(undefined)
      setEditError(undefined)
      toast.success('Route updated', {
        description: `${result.name} has been updated.`,
      })
    } catch (err: unknown) {
      setEditError(err instanceof Error ? err.message : 'Failed to update route.')
    }
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
        <Button onClick={() => setCreateDialogOpen(true)} disabled={loading}>
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
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
            loading={loading}
            deletingId={deletingId}
          />
        </CardContent>
      </Card>

      {/* Create Route Dialog */}
      <RouteFormDialog
        open={createDialogOpen}
        onClose={() => {
          setCreateDialogOpen(false)
          setCreateError(undefined)
        }}
        onSubmit={handleCreate}
        error={createError}
      />

      {/* Edit Route Dialog */}
      <RouteFormDialog
        open={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false)
          setEditingRoute(undefined)
          setEditError(undefined)
        }}
        onSubmit={handleEditSubmit}
        route={editingRoute}
        error={editError}
      />

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
