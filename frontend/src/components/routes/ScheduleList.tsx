import { Calendar } from 'lucide-react'
import { ScheduleCard } from './ScheduleCard'
import type { ScheduleResponse } from '../../lib/api'

export interface ScheduleListProps {
  /**
   * Array of schedules to display
   */
  schedules: ScheduleResponse[]

  /**
   * Callback when edit is clicked
   */
  onEdit: (scheduleId: string) => void

  /**
   * Callback when delete is clicked
   */
  onDelete: (scheduleId: string) => void

  /**
   * Optional ID of schedule being deleted (to show loading state)
   */
  deletingScheduleId?: string | null
}

/**
 * Display a list of schedules
 *
 * Shows all schedules for a route with edit/delete actions.
 *
 * @example
 * <ScheduleList
 *   schedules={route.schedules}
 *   onEdit={(id) => setEditingSchedule(id)}
 *   onDelete={(id) => handleDeleteSchedule(id)}
 * />
 */
export function ScheduleList({
  schedules,
  onEdit,
  onDelete,
  deletingScheduleId = null,
}: ScheduleListProps) {
  if (schedules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
        <Calendar className="mb-4 h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <h3 className="mb-2 text-lg font-semibold">No schedules configured</h3>
        <p className="text-sm text-muted-foreground">
          Add a schedule to specify when this route should be monitored for disruptions.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {schedules.map((schedule) => (
        <ScheduleCard
          key={schedule.id}
          daysOfWeek={schedule.days_of_week}
          startTime={schedule.start_time}
          endTime={schedule.end_time}
          onEdit={() => onEdit(schedule.id)}
          onDelete={() => onDelete(schedule.id)}
          isDeleting={deletingScheduleId === schedule.id}
        />
      ))}
    </div>
  )
}
