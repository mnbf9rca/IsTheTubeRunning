import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ChevronRight, Edit, Trash2, Plus } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Switch } from '../components/ui/switch'
import { Label } from '../components/ui/label'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs'
import { SegmentBuilder } from '../components/routes/SegmentBuilder'
import { ScheduleForm } from '../components/routes/ScheduleForm'
import { ScheduleList } from '../components/routes/ScheduleList'
import { RouteFormDialog } from '../components/routes/RouteFormDialog'
import { useTflData } from '../hooks/useTflData'
import {
  type RouteResponse,
  type SegmentRequest,
  type CreateScheduleRequest,
  type UpdateScheduleRequest,
  ApiError,
  getRoute,
  updateRoute,
  deleteRoute,
  upsertSegments,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  validateRoute as apiValidateRoute,
} from '../lib/api'
import type { RouteFormData } from '../components/routes/RouteFormDialog'

export function RouteDetails() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Route state
  const [route, setRoute] = useState<RouteResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  // UI state
  const [isEditingMetadata, setIsEditingMetadata] = useState(false)
  const [isEditingSegments, setIsEditingSegments] = useState(false)
  const [showAddSchedule, setShowAddSchedule] = useState(false)
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null)
  const [deletingScheduleId, setDeletingScheduleId] = useState<string | null>(null)

  // TfL data
  const tflData = useTflData()

  // Fetch route data
  useEffect(() => {
    if (!id) return

    const fetchRoute = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await getRoute(id)
        setRoute(data)
      } catch (err) {
        setError(err as ApiError)
      } finally {
        setLoading(false)
      }
    }

    fetchRoute()
  }, [id])

  const handleToggleActive = async () => {
    if (!route) return

    try {
      const updated = await updateRoute(route.id, { active: !route.active })
      setRoute(updated)
    } catch (err) {
      console.error('Failed to toggle active status:', err)
      setError(err as ApiError)
    }
  }

  const handleUpdateMetadata = async (data: RouteFormData) => {
    if (!route) return

    const updated = await updateRoute(route.id, {
      name: data.name,
      description: data.description,
      active: data.active,
    })
    setRoute(updated)
    setIsEditingMetadata(false)
  }

  const handleDeleteRoute = async () => {
    if (!route) return
    if (!confirm(`Are you sure you want to delete "${route.name}"?`)) return

    try {
      await deleteRoute(route.id)
      navigate('/routes')
    } catch (err) {
      console.error('Failed to delete route:', err)
    }
  }

  const handleSaveSegments = async (segments: SegmentRequest[]) => {
    if (!route) return

    const updatedSegments = await upsertSegments(route.id, segments)
    setRoute({ ...route, segments: updatedSegments })
    setIsEditingSegments(false)
  }

  const handleValidateRoute = async (segments: SegmentRequest[]) => {
    const validation = await apiValidateRoute(segments)
    return validation
  }

  const handleCreateSchedule = async (data: CreateScheduleRequest) => {
    if (!route) return

    const newSchedule = await createSchedule(route.id, data)
    setRoute({ ...route, schedules: [...route.schedules, newSchedule] })
    setShowAddSchedule(false)
  }

  const handleUpdateSchedule = async (scheduleId: string, data: UpdateScheduleRequest) => {
    if (!route) return

    const updatedSchedule = await updateSchedule(route.id, scheduleId, data)
    setRoute({
      ...route,
      schedules: route.schedules.map((s) => (s.id === scheduleId ? updatedSchedule : s)),
    })
    setEditingScheduleId(null)
  }

  const handleDeleteSchedule = async (scheduleId: string) => {
    if (!route) return
    if (!confirm('Are you sure you want to delete this schedule?')) return

    try {
      setDeletingScheduleId(scheduleId)
      await deleteSchedule(route.id, scheduleId)
      setRoute({
        ...route,
        schedules: route.schedules.filter((s) => s.id !== scheduleId),
      })
    } catch (err) {
      console.error('Failed to delete schedule:', err)
    } finally {
      setDeletingScheduleId(null)
    }
  }

  // Loading state
  if (loading || tflData.loading) {
    return (
      <div className="container max-w-5xl py-8">
        <div className="text-center">Loading route details...</div>
      </div>
    )
  }

  // Error state
  if (error || tflData.error) {
    return (
      <div className="container max-w-5xl py-8">
        <Alert variant="destructive">
          <AlertDescription>
            {error?.message || tflData.error?.message || 'Failed to load route'}
          </AlertDescription>
        </Alert>
        <Button onClick={() => navigate('/routes')} className="mt-4">
          Back to Routes
        </Button>
      </div>
    )
  }

  // No route found
  if (!route) {
    return (
      <div className="container max-w-5xl py-8">
        <Alert>
          <AlertDescription>Route not found</AlertDescription>
        </Alert>
        <Button onClick={() => navigate('/routes')} className="mt-4">
          Back to Routes
        </Button>
      </div>
    )
  }

  const editingSchedule = route.schedules.find((s) => s.id === editingScheduleId)

  return (
    <div className="container max-w-5xl py-8">
      {/* Breadcrumb */}
      <nav
        className="mb-4 flex items-center gap-2 text-sm text-muted-foreground"
        aria-label="Breadcrumb"
      >
        <Link to="/routes" className="hover:text-foreground">
          Routes
        </Link>
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
        <span className="text-foreground">{route.name}</span>
      </nav>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold">{route.name}</h1>
          {route.description && <p className="mt-1 text-muted-foreground">{route.description}</p>}
        </div>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setIsEditingMetadata(true)}>
            <Edit className="mr-2 h-4 w-4" />
            Edit
          </Button>
          <Button variant="destructive" onClick={handleDeleteRoute}>
            <Trash2 className="mr-2 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {/* Active Toggle */}
      <div className="mb-6 flex items-center gap-2">
        <Switch id="active" checked={route.active} onCheckedChange={handleToggleActive} />
        <Label htmlFor="active">{route.active ? 'Route is active' : 'Route is inactive'}</Label>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="segments">Segments ({route.segments.length})</TabsTrigger>
          <TabsTrigger value="schedules">Schedules ({route.schedules.length})</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border p-4">
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">Segments</h3>
              <p className="text-2xl font-bold">{route.segments.length}</p>
            </div>
            <div className="rounded-lg border p-4">
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">Schedules</h3>
              <p className="text-2xl font-bold">{route.schedules.length}</p>
            </div>
          </div>
        </TabsContent>

        {/* Segments Tab */}
        <TabsContent value="segments" className="space-y-4">
          {isEditingSegments ? (
            <SegmentBuilder
              routeId={route.id}
              initialSegments={route.segments}
              lines={tflData.lines || []}
              stations={tflData.stations || []}
              getNextStations={tflData.getNextStations}
              getLinesForStation={tflData.getLinesForStation}
              onValidate={handleValidateRoute}
              onSave={handleSaveSegments}
              onCancel={() => setIsEditingSegments(false)}
            />
          ) : (
            <div className="space-y-4">
              <Button onClick={() => setIsEditingSegments(true)}>
                <Edit className="mr-2 h-4 w-4" />
                Edit Segments
              </Button>
              {route.segments.length === 0 ? (
                <Alert>
                  <AlertDescription>
                    No segments configured. Click "Edit Segments" to build your route.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="text-sm text-muted-foreground">
                  {route.segments.length} segment{route.segments.length !== 1 ? 's' : ''} configured
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* Schedules Tab */}
        <TabsContent value="schedules" className="space-y-4">
          {!showAddSchedule && !editingScheduleId && (
            <Button onClick={() => setShowAddSchedule(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Schedule
            </Button>
          )}

          {showAddSchedule && (
            <ScheduleForm
              onSave={handleCreateSchedule}
              onCancel={() => setShowAddSchedule(false)}
            />
          )}

          {editingScheduleId && editingSchedule && (
            <ScheduleForm
              initialDays={editingSchedule.days_of_week}
              initialStartTime={editingSchedule.start_time.substring(0, 5)}
              initialEndTime={editingSchedule.end_time.substring(0, 5)}
              onSave={(data) => handleUpdateSchedule(editingScheduleId, data)}
              onCancel={() => setEditingScheduleId(null)}
              isEditing={true}
            />
          )}

          <ScheduleList
            schedules={route.schedules}
            onEdit={setEditingScheduleId}
            onDelete={handleDeleteSchedule}
            deletingScheduleId={deletingScheduleId}
          />
        </TabsContent>
      </Tabs>

      {/* Edit Metadata Dialog */}
      {isEditingMetadata && (
        <RouteFormDialog
          route={route}
          open={isEditingMetadata}
          onClose={() => setIsEditingMetadata(false)}
          onSubmit={handleUpdateMetadata}
        />
      )}
    </div>
  )
}
