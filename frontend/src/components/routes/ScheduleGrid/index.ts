/**
 * ScheduleGrid component barrel export
 *
 * Provides clean imports for the schedule grid component and related utilities.
 */

export { ScheduleGrid } from './ScheduleGrid'
export type { ScheduleGridProps } from './ScheduleGrid'

export { useScheduleGridState } from './hooks/useScheduleGridState'
export type {
  UseScheduleGridStateOptions,
  UseScheduleGridStateReturn,
} from './hooks/useScheduleGridState'

export {
  type DayCode,
  type TimeSlotIndex,
  type CellId,
  type GridSelection,
  type TimeBlock,
  type ValidationResult,
  DAYS,
  DAY_LABELS,
  SLOTS_PER_DAY,
  MINUTES_PER_SLOT,
  cellKey,
  parseKey,
} from './types'

export {
  slotToTime,
  timeToSlot,
  selectionToBlocks,
  gridToSchedules,
  schedulesToGrid,
} from './transforms'

export {
  toggleCell,
  isSelected,
  selectRange,
  clearSelection,
  selectDay,
  deselectDay,
  selectTimeSlot,
  deselectTimeSlot,
  isDaySelected,
  isTimeSlotSelected,
} from './selection'

export { validateNotEmpty, validateMaxSchedules, validateAll } from './validation'
