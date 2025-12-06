import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ChevronRight, Trash2 } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Label } from '../components/ui/label'
import { Textarea } from '../components/ui/textarea'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Card } from '../components/ui/card'
import { SegmentBuilder } from '../components/routes/SegmentBuilder/SegmentBuilder'
import {
  ScheduleGrid,
  gridToSchedules,
  validateNotEmpty,
  type GridSelection,
} from '../components/routes/ScheduleGrid'
import { useTflData } from '../hooks/useTflData'
import { useContacts } from '../hooks/useContacts'
import type {
  SegmentRequest,
  CreateNotificationPreferenceRequest,
  NotificationMethod,
} from '@/types'
import {
  ApiError,
  createRoute,
  upsertSegments,
  createSchedule,
  createNotificationPreference,
  validateRoute as apiValidateRoute,
  getRoutes,
} from '../lib/api'

interface LocalNotificationPreference {
  id: string // Temporary local ID
  method: NotificationMethod
  target_email_id: string | null
  target_phone_id: string | null
}

export function CreateRoute() {
  const navigate = useNavigate()
  const tflData = useTflData()
  const { contacts, loading: contactsLoading } = useContacts()

  // Route metadata state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  // Journey (segments) state
  const [segments, setSegments] = useState<SegmentRequest[]>([])

  // Alert configuration state (using grid selection for schedules)
  const [scheduleSelection, setScheduleSelection] = useState<GridSelection>(new Set())
  const [notifications, setNotifications] = useState<LocalNotificationPreference[]>([])
  const [selectedContactId, setSelectedContactId] = useState<string>('')
  const [selectedMethod, setSelectedMethod] = useState<NotificationMethod>('email')

  // UI state
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleValidateRoute = async (segmentsToValidate: SegmentRequest[]) => {
    const validation = await apiValidateRoute(segmentsToValidate)
    return validation
  }

  const handleSaveSegments = async (newSegments: SegmentRequest[]) => {
    setSegments(newSegments)
  }

  const handleAddNotification = () => {
    if (!selectedContactId) {
      setError('Please select a contact')
      return
    }

    // Check if already added
    const isDuplicate = notifications.some(
      (n) =>
        (n.target_email_id === selectedContactId || n.target_phone_id === selectedContactId) &&
        n.method === selectedMethod
    )

    if (isDuplicate) {
      setError('This contact is already added with the same method')
      return
    }

    const newNotification: LocalNotificationPreference = {
      id: `temp-${Date.now()}`,
      method: selectedMethod,
      target_email_id: selectedMethod === 'email' ? selectedContactId : null,
      target_phone_id: selectedMethod === 'sms' ? selectedContactId : null,
    }

    setNotifications([...notifications, newNotification])
    setSelectedContactId('')
    setError(null)
  }

  const handleDeleteNotification = (notificationId: string) => {
    setNotifications(notifications.filter((n) => n.id !== notificationId))
  }

  const handleCreateRoute = async () => {
    // Validation
    if (!name.trim()) {
      setError('Route name is required')
      return
    }

    if (segments.length < 2) {
      setError('Your journey must have at least 2 stations')
      return
    }

    setIsCreating(true)
    setError(null)

    try {
      // Check for duplicate route name
      const existingRoutes = await getRoutes()
      if (existingRoutes.some((r) => r.name.toLowerCase() === name.trim().toLowerCase())) {
        setError('A route with this name already exists. Please choose a different name.')
        setIsCreating(false)
        return
      }

      // 1. Create the route (metadata only)
      const route = await createRoute({
        name: name.trim(),
        description: description.trim() || undefined,
        active: true,
        timezone: 'Europe/London',
      })

      // 2. Add segments
      await upsertSegments(route.id, segments)

      // 3. Add schedules (convert grid selection to schedules)
      // Validate that at least one time slot is selected
      const validationResult = validateNotEmpty(scheduleSelection)
      if (!validationResult.valid) {
        setError(validationResult.error!)
        setIsCreating(false)
        return
      }

      const schedules = gridToSchedules(scheduleSelection)
      for (const schedule of schedules) {
        await createSchedule(route.id, schedule)
      }

      // 4. Add notification preferences
      for (const notification of notifications) {
        const data: CreateNotificationPreferenceRequest = {
          method: notification.method,
        }
        if (notification.target_email_id) {
          data.target_email_id = notification.target_email_id
        } else if (notification.target_phone_id) {
          data.target_phone_id = notification.target_phone_id
        }
        await createNotificationPreference(route.id, data)
      }

      // Navigate to the new route
      navigate(`/routes/${route.id}`)
    } catch (err) {
      console.error('Failed to create route:', err)
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Failed to create route. Please try again.')
      }
      setIsCreating(false)
    }
  }

  // Loading state
  if (tflData.loading || contactsLoading) {
    return (
      <div className="container max-w-5xl py-8">
        <div className="text-center">Loading...</div>
      </div>
    )
  }

  // Error state
  if (tflData.error) {
    return (
      <div className="container max-w-5xl py-8">
        <Alert variant="destructive">
          <AlertDescription>{tflData.error.message}</AlertDescription>
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
        <span className="text-foreground">Create New Route</span>
      </nav>

      {/* Header */}
      <h1 className="mb-6 text-3xl font-bold">Create New Route</h1>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-8">
        {/* Route Details Section */}
        <Card className="p-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">
                Route Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Home to Work"
                maxLength={255}
                required
              />
            </div>
            <div>
              <Label htmlFor="description">Description (Optional)</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Add any notes about this route..."
                rows={3}
              />
            </div>
          </div>
        </Card>

        {/* Your Journey Section */}
        <div>
          <h2 className="mb-4 text-2xl font-semibold">Your Journey</h2>
          <Card className="p-6">
            <SegmentBuilder
              routeId=""
              initialSegments={segments.map((seg, index) => ({
                id: `temp-${index}`,
                ...seg,
                line_tfl_id: seg.line_tfl_id ?? null,
              }))}
              lines={tflData.lines || []}
              stations={tflData.stations || []}
              getLinesForStation={tflData.getLinesForStation}
              getNextStations={tflData.getNextStations}
              onValidate={handleValidateRoute}
              onSave={handleSaveSegments}
              onCancel={() => {}}
            />
          </Card>
        </div>

        {/* When to Alert Section */}
        <div id="active-times-section">
          <h2 className="mb-4 text-2xl font-semibold">When to Alert</h2>

          {/* Active Times Subsection */}
          <div className="mb-6">
            <h3 className="mb-3 text-lg font-medium">Active Times</h3>
            <ScheduleGrid
              initialSelection={scheduleSelection}
              onChange={setScheduleSelection}
              disabled={false}
            />
          </div>

          {/* Send Alerts To Subsection */}
          <div>
            <h3 className="mb-3 text-lg font-medium">Send Alerts To</h3>
            <Card className="p-6">
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
                        // Auto-detect method based on selected contact
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

              {notifications.length === 0 ? (
                <Alert>
                  <AlertDescription>
                    No contacts selected. Add contacts to receive alerts when disruptions affect
                    this route.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="space-y-2">
                  {notifications.map((notification) => {
                    // Find contact details
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
                      <Card key={notification.id} className="flex items-center justify-between p-3">
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
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </Card>
                    )
                  })}
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate('/routes')} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleCreateRoute} disabled={isCreating}>
            {isCreating ? 'Creating...' : 'Create Route'}
          </Button>
        </div>
      </div>
    </div>
  )
}
