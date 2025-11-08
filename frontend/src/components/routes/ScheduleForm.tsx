import { useState } from 'react'
import { Save, X } from 'lucide-react'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { Input } from '../ui/input'
import { Alert, AlertDescription } from '../ui/alert'
import { Card } from '../ui/card'

const DAYS_OF_WEEK = [
  { code: 'MON', label: 'Mon' },
  { code: 'TUE', label: 'Tue' },
  { code: 'WED', label: 'Wed' },
  { code: 'THU', label: 'Thu' },
  { code: 'FRI', label: 'Fri' },
  { code: 'SAT', label: 'Sat' },
  { code: 'SUN', label: 'Sun' },
]

export interface ScheduleFormProps {
  /**
   * Initial days (for editing existing schedule)
   */
  initialDays?: string[]

  /**
   * Initial start time (HH:MM format, for editing)
   */
  initialStartTime?: string

  /**
   * Initial end time (HH:MM format, for editing)
   */
  initialEndTime?: string

  /**
   * Callback when schedule is saved
   */
  onSave: (data: { days_of_week: string[]; start_time: string; end_time: string }) => Promise<void>

  /**
   * Callback when form is cancelled
   */
  onCancel: () => void

  /**
   * Whether this is editing an existing schedule (vs creating new)
   */
  isEditing?: boolean
}

/**
 * Form for creating or editing a schedule
 *
 * Allows selection of days and time range for when the route is active.
 *
 * @example
 * <ScheduleForm
 *   onSave={async (data) => await createSchedule(routeId, data)}
 *   onCancel={() => setShowForm(false)}
 * />
 */
export function ScheduleForm({
  initialDays = [],
  initialStartTime = '09:00',
  initialEndTime = '17:00',
  onSave,
  onCancel,
  isEditing = false,
}: ScheduleFormProps) {
  const [selectedDays, setSelectedDays] = useState<Set<string>>(new Set(initialDays))
  const [startTime, setStartTime] = useState(initialStartTime)
  const [endTime, setEndTime] = useState(initialEndTime)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toggleDay = (dayCode: string) => {
    const newDays = new Set(selectedDays)
    if (newDays.has(dayCode)) {
      newDays.delete(dayCode)
    } else {
      newDays.add(dayCode)
    }
    setSelectedDays(newDays)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    // Validation
    if (selectedDays.size === 0) {
      setError('Please select at least one day')
      return
    }

    if (!startTime || !endTime) {
      setError('Please enter both start and end times')
      return
    }

    // Convert HH:MM to HH:MM:SS for backend
    const startTimeWithSeconds = `${startTime}:00`
    const endTimeWithSeconds = `${endTime}:00`

    // Check end time is after start time
    if (endTimeWithSeconds <= startTimeWithSeconds) {
      setError('End time must be after start time')
      return
    }

    try {
      setIsSaving(true)
      await onSave({
        days_of_week: Array.from(selectedDays),
        start_time: startTimeWithSeconds,
        end_time: endTimeWithSeconds,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schedule')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card className="p-4">
      <h3 className="mb-4 text-sm font-medium">{isEditing ? 'Edit Schedule' : 'Add Schedule'}</h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Days of week */}
        <div className="space-y-2">
          <Label>Days of Week</Label>
          <div className="grid grid-cols-7 gap-2">
            {DAYS_OF_WEEK.map((day) => (
              <button
                key={day.code}
                type="button"
                onClick={() => toggleDay(day.code)}
                className={`rounded-md border px-2 py-2 text-sm font-medium transition-colors ${
                  selectedDays.has(day.code)
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-input bg-background hover:bg-accent hover:text-accent-foreground'
                }`}
                aria-pressed={selectedDays.has(day.code)}
                aria-label={`Toggle ${day.label}`}
              >
                {day.label}
              </button>
            ))}
          </div>
        </div>

        {/* Time inputs */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="start-time">Start Time</Label>
            <Input
              id="start-time"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="end-time">End Time</Label>
            <Input
              id="end-time"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Error display */}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Action buttons */}
        <div className="flex gap-2">
          <Button type="submit" disabled={isSaving}>
            <Save className="mr-2 h-4 w-4" />
            {isSaving ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSaving}>
            <X className="mr-2 h-4 w-4" />
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  )
}
