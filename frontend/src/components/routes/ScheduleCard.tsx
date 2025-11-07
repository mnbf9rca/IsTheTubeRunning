import { Clock, Edit, Trash2 } from 'lucide-react'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Card } from '../ui/card'

export interface ScheduleCardProps {
  /**
   * Days of week (e.g., ['MON', 'TUE', 'WED'])
   */
  daysOfWeek: string[]

  /**
   * Start time (HH:MM:SS format)
   */
  startTime: string

  /**
   * End time (HH:MM:SS format)
   */
  endTime: string

  /**
   * Callback when edit button is clicked
   */
  onEdit: () => void

  /**
   * Callback when delete button is clicked
   */
  onDelete: () => void

  /**
   * Whether delete operation is in progress
   */
  isDeleting?: boolean
}

/**
 * Display a single schedule
 *
 * Shows days of week as badges and time range.
 *
 * @example
 * <ScheduleCard
 *   daysOfWeek={['MON', 'TUE', 'WED', 'THU', 'FRI']}
 *   startTime="09:00:00"
 *   endTime="17:00:00"
 *   onEdit={() => handleEdit(schedule.id)}
 *   onDelete={() => handleDelete(schedule.id)}
 * />
 */
export function ScheduleCard({
  daysOfWeek,
  startTime,
  endTime,
  onEdit,
  onDelete,
  isDeleting = false,
}: ScheduleCardProps) {
  // Format time from HH:MM:SS to HH:MM
  const formatTime = (time: string) => {
    return time.substring(0, 5) // Take first 5 characters (HH:MM)
  }

  // Map day codes to short labels
  const dayLabels: Record<string, string> = {
    MON: 'Mon',
    TUE: 'Tue',
    WED: 'Wed',
    THU: 'Thu',
    FRI: 'Fri',
    SAT: 'Sat',
    SUN: 'Sun',
  }

  return (
    <Card className="flex items-center gap-4 p-4">
      {/* Days */}
      <div className="flex flex-1 flex-wrap gap-1.5">
        {daysOfWeek.map((day) => (
          <Badge key={day} variant="secondary" className="text-xs">
            {dayLabels[day] || day}
          </Badge>
        ))}
      </div>

      {/* Time range */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Clock className="h-4 w-4" aria-hidden="true" />
        <span>
          {formatTime(startTime)} - {formatTime(endTime)}
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={onEdit}
          disabled={isDeleting}
          aria-label="Edit schedule"
          className="h-8 w-8"
        >
          <Edit className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          disabled={isDeleting}
          aria-label="Delete schedule"
          className="h-8 w-8"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  )
}
