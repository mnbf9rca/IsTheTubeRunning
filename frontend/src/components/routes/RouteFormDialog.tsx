import { useState, useEffect } from 'react'
import { MapPin } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Alert, AlertDescription } from '../ui/alert'
import { Switch } from '../ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import type { RouteResponse } from '../../lib/api'

export interface RouteFormDialogProps {
  open: boolean
  onClose: () => void
  onSubmit: (data: RouteFormData) => Promise<void>
  route?: RouteResponse // If provided, edit mode
}

export interface RouteFormData {
  name: string
  description?: string
  active: boolean
  timezone: string
}

// Common timezones for TfL (UK-focused)
const TIMEZONES = [
  'Europe/London',
  'Europe/Dublin',
  'Europe/Paris',
  'Europe/Berlin',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Tokyo',
  'Australia/Sydney',
]

/**
 * RouteFormDialog component for creating or editing a route
 *
 * @param open - Whether the dialog is open
 * @param onClose - Callback when dialog should close
 * @param onSubmit - Async callback to submit the form data (throws on error)
 * @param route - If provided, edit this route (otherwise create new)
 */
export function RouteFormDialog({ open, onClose, onSubmit, route }: RouteFormDialogProps) {
  const isEditMode = !!route

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [active, setActive] = useState(true)
  const [timezone, setTimezone] = useState('Europe/London')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Populate form when editing
  useEffect(() => {
    if (route) {
      setName(route.name)
      setDescription(route.description || '')
      setActive(route.active)
      setTimezone(route.timezone)
    } else {
      // Reset for create mode
      setName('')
      setDescription('')
      setActive(true)
      setTimezone('Europe/London')
    }
  }, [route, open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Basic client-side validation
    if (!name.trim()) {
      setError('Please enter a route name')
      return
    }

    if (name.trim().length > 255) {
      setError('Route name must be 255 characters or less')
      return
    }

    try {
      setIsSubmitting(true)
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        active,
        timezone,
      })
      // Success - close dialog and reset
      handleClose()
    } catch (err) {
      // Handle API errors
      if (err && typeof err === 'object' && 'status' in err) {
        const apiError = err as { status: number; data?: { detail?: string } }
        if (apiError.status === 400) {
          const detail = apiError.data?.detail || 'Invalid input'
          setError(detail)
        } else if (apiError.status === 404) {
          setError('Route not found.')
        } else {
          setError('An error occurred. Please try again.')
        }
      } else {
        setError('An error occurred. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isEditMode) {
      setName('')
      setDescription('')
      setActive(true)
      setTimezone('Europe/London')
    }
    setError(null)
    onClose()
  }

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      handleClose()
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" aria-hidden="true" />
            {isEditMode ? 'Edit Route' : 'Create Route'}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? 'Update the details of your route.'
              : 'Create a new route to monitor for disruptions. You can add segments and schedules later.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="route-name">Name *</Label>
              <Input
                id="route-name"
                type="text"
                placeholder="Home to Work"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={isSubmitting}
                autoFocus
                maxLength={255}
                aria-describedby={error ? 'route-error' : undefined}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="route-description">Description</Label>
              <Input
                id="route-description"
                type="text"
                placeholder="My daily commute via Victoria line"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={isSubmitting}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="route-timezone">Timezone</Label>
              <Select value={timezone} onValueChange={setTimezone} disabled={isSubmitting}>
                <SelectTrigger id="route-timezone">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONES.map((tz) => (
                    <SelectItem key={tz} value={tz}>
                      {tz}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label htmlFor="route-active">Active</Label>
                <p className="text-sm text-muted-foreground">
                  Active routes will receive disruption alerts
                </p>
              </div>
              <Switch
                id="route-active"
                checked={active}
                onCheckedChange={setActive}
                disabled={isSubmitting}
              />
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription id="route-error">{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? isEditMode
                  ? 'Saving...'
                  : 'Creating...'
                : isEditMode
                  ? 'Save'
                  : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
