import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ChevronRight, Edit, Trash2, X } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Textarea } from '../components/ui/textarea'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Card } from '../components/ui/card'
import { SegmentBuilder } from '../components/routes/SegmentBuilder/SegmentBuilder'
import { SegmentDisplay } from '../components/routes/SegmentDisplay'
import {
  ScheduleGrid,
  schedulesToGrid,
  gridToSchedules,
  validateNotEmpty,
  type GridSelection,
} from '../components/routes/ScheduleGrid'
import { NotificationDisplay } from '../components/routes/NotificationDisplay'
import { useTflData } from '../hooks/useTflData'
import { useContacts } from '../hooks/useContacts'
import { segmentResponseToRequest } from '../lib/segment-utils'
import type {
  RouteResponse,
  SegmentRequest,
  NotificationPreferenceResponse,
  CreateNotificationPreferenceRequest,
  NotificationMethod,
} from '@/types'
import {
  ApiError,
  getRoute,
  updateRoute,
  deleteRoute,
  upsertSegments,
  upsertSchedules,
  getNotificationPreferences,
  createNotificationPreference,
  deleteNotificationPreference,
  validateRoute as apiValidateRoute,
} from '../lib/api'

export function RouteDetails() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const tflData = useTflData()
  const { contacts, loading: contactsLoading } = useContacts()

  // Route state
  const [route, setRoute] = useState<RouteResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  // Notification preferences state
  const [notifications, setNotifications] = useState<NotificationPreferenceResponse[]>([])
  const [notificationsLoading, setNotificationsLoading] = useState(true)

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false)

  // Editable fields (only used when isEditing === true)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')

  // Segments editing
  const [editSegments, setEditSegments] = useState<SegmentRequest[]>([])

  // Schedules editing (using grid selection)
  const [editScheduleSelection, setEditScheduleSelection] = useState<GridSelection>(new Set())

  // Notifications editing
  const [editNotifications, setEditNotifications] = useState<NotificationPreferenceResponse[]>([])
  const [selectedContactId, setSelectedContactId] = useState<string>('')
  const [selectedMethod, setSelectedMethod] = useState<NotificationMethod>('email')

  // Fetch route data
  useEffect(() => {
    if (!id) return

    const fetchRouteData = async () => {
      try {
        setLoading(true)
        setError(null)
        const routeData = await getRoute(id)
        setRoute(routeData)

        // Fetch notification preferences
        setNotificationsLoading(true)
        const notifData = await getNotificationPreferences(id)
        setNotifications(notifData)
        setNotificationsLoading(false)
      } catch (err) {
        setError(err as ApiError)
      } finally {
        setLoading(false)
      }
    }

    fetchRouteData()
  }, [id])

  const handleStartEditing = () => {
    if (!route) return
    setEditName(route.name)
    setEditDescription(route.description || '')
    setEditSegments(route.segments.map(segmentResponseToRequest))
    setEditScheduleSelection(schedulesToGrid(route.schedules))
    setEditNotifications([...notifications])
    setIsEditing(true)
  }

  const handleCancelEditing = () => {
    setIsEditing(false)
    setSelectedContactId('')
  }

  const handleSaveChanges = async () => {
    if (!route || !id) return

    try {
      // 1. Update route metadata
      const updatedRoute = await updateRoute(id, {
        name: editName.trim(),
        description: editDescription.trim() || undefined,
      })

      // 2. Update segments
      const updatedSegments = await upsertSegments(id, editSegments)

      // 3. Sync schedules (atomically replace all - Issue #359)
      // Validate that at least one time slot is selected
      const validationResult = validateNotEmpty(editScheduleSelection)
      if (!validationResult.valid) {
        setError(new ApiError(400, validationResult.error!))
        return
      }

      // Atomically replace all schedules with single API call
      const newSchedules = gridToSchedules(editScheduleSelection)
      const createdSchedules = await upsertSchedules(id, newSchedules)

      // 4. Sync notifications (delete removed, add new ones)
      // Delete notifications that were removed
      for (const oldNotif of notifications) {
        if (!editNotifications.find((n) => n.id === oldNotif.id)) {
          await deleteNotificationPreference(id, oldNotif.id)
        }
      }

      // Add new notifications
      for (const newNotif of editNotifications) {
        if (!notifications.find((n) => n.id === newNotif.id)) {
          // This is a new one, create it
          const data: CreateNotificationPreferenceRequest = {
            method: newNotif.method,
          }
          if (newNotif.target_email_id) {
            data.target_email_id = newNotif.target_email_id
          } else if (newNotif.target_phone_id) {
            data.target_phone_id = newNotif.target_phone_id
          }
          await createNotificationPreference(id, data)
        }
      }

      // Refresh notification preferences
      const refreshedNotifications = await getNotificationPreferences(id)
      setNotifications(refreshedNotifications)

      // Update local state
      setRoute({
        ...updatedRoute,
        segments: updatedSegments,
        schedules: createdSchedules,
      })

      setIsEditing(false)
    } catch (err) {
      console.error('Failed to save changes:', err)
      setError(err as ApiError)
    }
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

  const handleValidateRoute = async (segments: SegmentRequest[]) => {
    const validation = await apiValidateRoute(segments)
    return validation
  }

  const handleSaveSegments = async (newSegments: SegmentRequest[]) => {
    setEditSegments(newSegments)
  }

  const handleAddNotification = () => {
    if (!selectedContactId) {
      return
    }

    // Check if already added
    const isDuplicate = editNotifications.some(
      (n) =>
        (n.target_email_id === selectedContactId || n.target_phone_id === selectedContactId) &&
        n.method === selectedMethod
    )

    if (isDuplicate) {
      return
    }

    const newNotification: NotificationPreferenceResponse = {
      id: `temp-${Date.now()}`,
      route_id: route?.id || '',
      method: selectedMethod,
      target_email_id: selectedMethod === 'email' ? selectedContactId : null,
      target_phone_id: selectedMethod === 'sms' ? selectedContactId : null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    setEditNotifications([...editNotifications, newNotification])
    setSelectedContactId('')
  }

  const handleDeleteNotification = (notificationId: string) => {
    setEditNotifications(editNotifications.filter((n) => n.id !== notificationId))
  }

  // Loading state
  if (loading || tflData.loading || notificationsLoading || contactsLoading) {
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

  // Get verified contacts for notification method selector
  const verifiedEmails = contacts?.emails?.filter((e) => e.verified) || []
  const verifiedPhones = contacts?.phones?.filter((p) => p.verified) || []
  const hasVerifiedContacts = verifiedEmails.length > 0 || verifiedPhones.length > 0

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

      <div className="space-y-8">
        {/* Route Details Section */}
        <div>
          <div className="mb-4 flex items-center justify-between">
            {!isEditing && (
              <>
                <div className="flex-1">
                  <h1 className="text-3xl font-bold">{route.name}</h1>
                  {route.description && (
                    <p className="mt-1 text-muted-foreground">{route.description}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={handleStartEditing}>
                    <Edit className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button variant="destructive" onClick={handleDeleteRoute}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </div>
              </>
            )}
          </div>

          {isEditing && (
            <Card className="p-6">
              <div className="space-y-4">
                <div>
                  <Label htmlFor="name">
                    Route Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    maxLength={255}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="description">Description (Optional)</Label>
                  <Textarea
                    id="description"
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={3}
                  />
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Your Journey Section */}
        <div>
          <h2 className="mb-4 text-2xl font-semibold">Your Journey</h2>
          <Card className="p-6">
            {isEditing ? (
              <SegmentBuilder
                routeId={route.id}
                initialSegments={route.segments}
                lines={tflData.lines || []}
                stations={tflData.stations || []}
                getLinesForStation={tflData.getLinesForStation}
                getNextStations={tflData.getNextStations}
                onValidate={handleValidateRoute}
                onSave={handleSaveSegments}
                onCancel={() => {}}
              />
            ) : (
              <SegmentDisplay
                segments={route.segments}
                lines={tflData.lines || []}
                stations={tflData.stations || []}
              />
            )}
          </Card>
        </div>

        {/* When to Alert Section */}
        <div>
          <h2 className="mb-4 text-2xl font-semibold">When to Alert</h2>

          {/* Active Times Subsection */}
          <div className="mb-6">
            <h3 className="mb-3 text-lg font-medium">Active Times</h3>
            {isEditing ? (
              <ScheduleGrid
                initialSelection={editScheduleSelection}
                onChange={setEditScheduleSelection}
                disabled={false}
              />
            ) : (
              <>
                {route.schedules.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      No active times configured. Edit this route to set when you want to receive
                      alerts.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <ScheduleGrid
                    initialSelection={schedulesToGrid(route.schedules)}
                    onChange={() => {}}
                    disabled={true}
                  />
                )}
              </>
            )}
          </div>

          {/* Send Alerts To Subsection */}
          <div>
            <h3 className="mb-3 text-lg font-medium">Send Alerts To</h3>
            <Card className="p-6">
              {isEditing && (
                <div className="mb-4 space-y-3">
                  <Label>Select Contact Method</Label>
                  {!hasVerifiedContacts ? (
                    <Alert>
                      <AlertDescription>
                        You need to add and verify contacts before you can receive alerts.{' '}
                        <Link to="/dashboard/contacts" className="underline">
                          Manage contacts
                        </Link>
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <div className="flex gap-2">
                      <select
                        value={selectedContactId}
                        onChange={(e) => {
                          const contactId = e.target.value
                          setSelectedContactId(contactId)
                          const isEmail = verifiedEmails.some((email) => email.id === contactId)
                          setSelectedMethod(isEmail ? 'email' : 'sms')
                        }}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <option value="">Select a contact...</option>
                        {verifiedEmails.length > 0 && (
                          <optgroup label="Email">
                            {verifiedEmails.map((email) => (
                              <option key={email.id} value={email.id}>
                                {email.email}
                              </option>
                            ))}
                          </optgroup>
                        )}
                        {verifiedPhones.length > 0 && (
                          <optgroup label="SMS">
                            {verifiedPhones.map((phone) => (
                              <option key={phone.id} value={phone.id}>
                                {phone.phone}
                              </option>
                            ))}
                          </optgroup>
                        )}
                      </select>
                      <Button onClick={handleAddNotification} disabled={!selectedContactId}>
                        Add
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {isEditing ? (
                editNotifications.length === 0 ? (
                  <Alert>
                    <AlertDescription>
                      No contacts selected. Add contacts to receive alerts when disruptions affect
                      this route.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="space-y-2">
                    {editNotifications.map((notification) => {
                      let contactText = 'Unknown'
                      if (notification.target_email_id) {
                        const email = verifiedEmails.find(
                          (e) => e.id === notification.target_email_id
                        )
                        if (email) contactText = email.email
                      } else if (notification.target_phone_id) {
                        const phone = verifiedPhones.find(
                          (p) => p.id === notification.target_phone_id
                        )
                        if (phone) contactText = phone.phone
                      }

                      return (
                        <Card
                          key={notification.id}
                          className="flex items-center justify-between p-3"
                        >
                          <div>
                            <div className="font-medium">{contactText}</div>
                            <div className="text-sm text-muted-foreground">
                              {notification.method.toUpperCase()}
                            </div>
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteNotification(notification.id)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </Card>
                      )
                    })}
                  </div>
                )
              ) : (
                <NotificationDisplay
                  preferences={notifications}
                  emails={contacts?.emails || []}
                  phones={contacts?.phones || []}
                />
              )}
            </Card>
          </div>
        </div>

        {/* Action Buttons (only in edit mode) */}
        {isEditing && (
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handleCancelEditing}>
              Cancel
            </Button>
            <Button onClick={handleSaveChanges}>Save Changes</Button>
          </div>
        )}
      </div>
    </div>
  )
}
