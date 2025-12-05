/**
 * Pure functions for transforming between grid selection and API schedule format
 *
 * These functions handle the bidirectional conversion:
 * - Grid selection (Set of cell keys) → API schedules
 * - API schedules → Grid selection
 *
 * All functions are pure (no side effects, no external state) and fully testable.
 *
 * @see ADR 11: Frontend State Management Pattern
 */

import {
  type GridSelection,
  type TimeBlock,
  type CreateScheduleRequest,
  type ScheduleResponse,
  type DayCode,
  type TimeSlotIndex,
  DAYS,
  MINUTES_PER_SLOT,
  cellKey,
  parseKey,
} from './types'

/**
 * Convert time slot index to HH:MM:SS time string
 *
 * @param slot Time slot index (0-95)
 * @returns Time string in HH:MM:SS format
 *
 * @example
 * slotToTime(0) // => '00:00:00'
 * slotToTime(1) // => '00:15:00'
 * slotToTime(48) // => '12:00:00'
 * slotToTime(95) // => '23:45:00'
 */
export function slotToTime(slot: TimeSlotIndex): string {
  const totalMinutes = slot * MINUTES_PER_SLOT
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:00`
}

/**
 * Convert HH:MM:SS time string to slot index
 *
 * Rounds down to the nearest 15-minute slot.
 *
 * @param time Time string in HH:MM:SS or HH:MM format
 * @returns Time slot index (0-95)
 *
 * @example
 * timeToSlot('00:00:00') // => 0
 * timeToSlot('00:15:00') // => 1
 * timeToSlot('12:00:00') // => 48
 * timeToSlot('23:45:00') // => 95
 * timeToSlot('09:22:00') // => 37 (rounds down to 09:15)
 */
export function timeToSlot(time: string): TimeSlotIndex {
  const [hoursStr, minutesStr] = time.split(':')
  const hours = parseInt(hoursStr, 10)
  const minutes = parseInt(minutesStr, 10)

  const totalMinutes = hours * 60 + minutes
  return Math.floor(totalMinutes / MINUTES_PER_SLOT)
}

/**
 * Get all selected slots for a specific day, sorted
 *
 * @param selection Grid selection
 * @param day Day to filter by
 * @returns Sorted array of slot indices for that day
 */
function getSlotsForDay(selection: GridSelection, day: DayCode): TimeSlotIndex[] {
  const slots: TimeSlotIndex[] = []

  for (const key of selection) {
    const cell = parseKey(key)
    if (cell.day === day) {
      slots.push(cell.slot)
    }
  }

  return slots.sort((a, b) => a - b)
}

/**
 * Group contiguous selected slots into time blocks
 *
 * Takes a sorted array of slot indices and groups them into continuous ranges.
 *
 * @param day Day of the week
 * @param slots Sorted array of slot indices
 * @returns Array of TimeBlock objects
 *
 * @example
 * groupIntoBlocks('MON', [0, 1, 2, 5, 6])
 * // => [
 * //   { day: 'MON', startSlot: 0, endSlot: 3 },
 * //   { day: 'MON', startSlot: 5, endSlot: 7 }
 * // ]
 */
function groupIntoBlocks(day: DayCode, slots: TimeSlotIndex[]): TimeBlock[] {
  if (slots.length === 0) {
    return []
  }

  const blocks: TimeBlock[] = []
  let startSlot = slots[0]
  let endSlot = slots[0] + 1

  for (let i = 1; i < slots.length; i++) {
    if (slots[i] === endSlot) {
      // Contiguous slot - extend current block
      endSlot = slots[i] + 1
    } else {
      // Gap found - finalize current block and start new one
      blocks.push({ day, startSlot, endSlot })
      startSlot = slots[i]
      endSlot = slots[i] + 1
    }
  }

  // Add final block
  blocks.push({ day, startSlot, endSlot })

  return blocks
}

/**
 * Convert grid selection to contiguous time blocks per day
 *
 * @param selection Grid selection
 * @returns Array of TimeBlock objects
 *
 * @example
 * const selection = new Set(['MON:0', 'MON:1', 'MON:5', 'TUE:48'])
 * selectionToBlocks(selection)
 * // => [
 * //   { day: 'MON', startSlot: 0, endSlot: 2 },
 * //   { day: 'MON', startSlot: 5, endSlot: 6 },
 * //   { day: 'TUE', startSlot: 48, endSlot: 49 }
 * // ]
 */
export function selectionToBlocks(selection: GridSelection): TimeBlock[] {
  const blocks: TimeBlock[] = []

  for (const day of DAYS) {
    const slots = getSlotsForDay(selection, day)
    if (slots.length > 0) {
      blocks.push(...groupIntoBlocks(day, slots))
    }
  }

  return blocks
}

/**
 * Convert grid selection to API schedule format
 *
 * Converts the grid selection into an array of schedule requests by:
 * 1. Grouping contiguous cells into time blocks per day
 * 2. Converting each block to a schedule with single-day array and time range
 *
 * @param selection Grid selection
 * @returns Array of CreateScheduleRequest objects
 *
 * @example
 * const selection = new Set(['MON:0', 'MON:1', 'TUE:48'])
 * gridToSchedules(selection)
 * // => [
 * //   { days_of_week: ['MON'], start_time: '00:00:00', end_time: '00:30:00' },
 * //   { days_of_week: ['TUE'], start_time: '12:00:00', end_time: '12:15:00' }
 * // ]
 */
export function gridToSchedules(selection: GridSelection): CreateScheduleRequest[] {
  const blocks = selectionToBlocks(selection)

  return blocks.map((block) => ({
    days_of_week: [block.day],
    start_time: slotToTime(block.startSlot),
    end_time: slotToTime(block.endSlot),
  }))
}

/**
 * Convert API schedules to grid selection
 *
 * Expands each schedule into individual cell selections:
 * - For each day in the schedule's days_of_week
 * - For each 15-minute slot between start_time and end_time
 * - Add the cell to the selection
 *
 * @param schedules Array of schedule responses from API
 * @returns Grid selection
 *
 * @example
 * const schedules = [
 *   { id: '1', days_of_week: ['MON', 'TUE'], start_time: '09:00:00', end_time: '10:00:00' }
 * ]
 * schedulesToGrid(schedules)
 * // => Set(['MON:36', 'MON:37', 'MON:38', 'MON:39',
 * //          'TUE:36', 'TUE:37', 'TUE:38', 'TUE:39'])
 */
export function schedulesToGrid(schedules: ScheduleResponse[]): GridSelection {
  const selection = new Set<string>()

  for (const schedule of schedules) {
    const startSlot = timeToSlot(schedule.start_time)
    const endSlot = timeToSlot(schedule.end_time)

    for (const day of schedule.days_of_week) {
      for (let slot = startSlot; slot < endSlot; slot++) {
        selection.add(cellKey(day as DayCode, slot))
      }
    }
  }

  return selection
}
