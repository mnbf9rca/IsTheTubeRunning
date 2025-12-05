/**
 * ScheduleGrid Component
 *
 * A grid-based UI for selecting time slots across days of the week.
 * - Columns: Days of the week (Mon-Sun)
 * - Rows: 15-minute time intervals (00:00-23:45)
 * - Interaction: Click to toggle cells, drag to select ranges
 *
 * @see Issue #356: Simplify alerting time
 */

import { type GridSelection, type DayCode, type CellId, DAYS, DAY_LABELS } from './types'
import { slotToTime } from './transforms'
import { useScheduleGridState } from './hooks/useScheduleGridState'
import { isSelected } from './selection'
import { Card } from '../../ui/card'

// Stable empty selection to avoid creating new Set instances on each render
const EMPTY_SELECTION: GridSelection = new Set()

export interface ScheduleGridProps {
  /** Initial selection (e.g., loaded from existing schedules) */
  initialSelection?: GridSelection

  /** Callback when selection changes */
  onChange: (selection: GridSelection) => void

  /** Whether grid is disabled */
  disabled?: boolean

  /** CSS class name for container */
  className?: string
}

/**
 * Main schedule grid component
 *
 * Renders a 7×96 grid where users can select time slots by clicking or dragging.
 *
 * @example
 * <ScheduleGrid
 *   initialSelection={schedulesToGrid(route.schedules)}
 *   onChange={(selection) => {
 *     const schedules = gridToSchedules(selection)
 *     // Save schedules...
 *   }}
 *   disabled={!isEditing}
 * />
 */
export function ScheduleGrid({
  initialSelection = EMPTY_SELECTION,
  onChange,
  disabled = false,
  className = '',
}: ScheduleGridProps) {
  const {
    previewSelection,
    isDragging,
    handleCellClick,
    handleDragStart,
    handleDragMove,
    handleDragEnd,
  } = useScheduleGridState({
    initialSelection,
    onChange,
    disabled,
  })

  return (
    <Card className={`p-4 ${className}`}>
      <div className="overflow-x-auto">
        <div className="inline-block min-w-full">
          {/* Grid container - transposed: days as rows, time as columns */}
          <div
            className="relative"
            style={{
              display: 'grid',
              gridTemplateColumns: '60px repeat(96, 15px)', // 96 × 15px = 1440px for time slots
              gridTemplateRows: 'auto repeat(7, 24px)', // Header + 7 days
              gap: '0',
            }}
            onMouseLeave={() => {
              if (isDragging) {
                handleDragEnd()
              }
            }}
          >
            {/* Top-left corner cell */}
            <div className="sticky top-0 left-0 z-20 bg-background border-b border-r border-border p-2 text-xs font-medium text-center">
              Day
            </div>

            {/* Time headers (96 columns for 15-min slots) */}
            {Array.from({ length: 96 }, (_, slot) => {
              const isHourMark = slot % 4 === 0
              const time = slotToTime(slot)
              return (
                <div
                  key={slot}
                  className={`sticky top-0 z-10 bg-background border-b border-border text-xs text-center ${
                    isHourMark ? 'font-medium border-l' : 'border-l-0'
                  }`}
                  style={{
                    width: '15px',
                    height: '24px',
                    writingMode: 'vertical-rl',
                    transform: 'rotate(180deg)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '2px 0',
                    fontSize: '10px',
                  }}
                >
                  {isHourMark ? time.substring(0, 5) : ''}
                </div>
              )
            })}

            {/* Day rows */}
            {DAYS.map((day) => (
              <DayRow
                key={day}
                day={day}
                previewSelection={previewSelection}
                disabled={disabled}
                isDragging={isDragging}
                onCellClick={handleCellClick}
                onCellMouseDown={handleDragStart}
                onCellMouseEnter={handleDragMove}
              />
            ))}
          </div>
        </div>
      </div>
    </Card>
  )
}

interface DayRowProps {
  day: DayCode
  previewSelection: GridSelection
  disabled: boolean
  isDragging: boolean
  onCellClick: (cell: CellId) => void
  onCellMouseDown: (cell: CellId) => void
  onCellMouseEnter: (cell: CellId) => void
}

/**
 * A single row of the grid (one day across all time slots)
 */
function DayRow({
  day,
  previewSelection,
  disabled,
  isDragging,
  onCellClick,
  onCellMouseDown,
  onCellMouseEnter,
}: DayRowProps) {
  return (
    <>
      {/* Day label */}
      <div
        className="sticky left-0 z-10 bg-background border-r border-t border-border p-1 text-xs font-medium text-center"
        style={{ height: '24px' }}
      >
        {DAY_LABELS[day]}
      </div>

      {/* Cells for each time slot */}
      {Array.from({ length: 96 }, (_, slot) => {
        const isHourMark = slot % 4 === 0
        return (
          <GridCell
            key={`${day}:${slot}`}
            day={day}
            slot={slot}
            isSelected={isSelected(previewSelection, { day, slot })}
            isHourMark={isHourMark}
            disabled={disabled}
            isDragging={isDragging}
            onClick={onCellClick}
            onMouseDown={onCellMouseDown}
            onMouseEnter={onCellMouseEnter}
          />
        )
      })}
    </>
  )
}

interface GridCellProps {
  day: DayCode
  slot: number
  isSelected: boolean
  isHourMark: boolean
  disabled: boolean
  isDragging: boolean
  onClick: (cell: CellId) => void
  onMouseDown: (cell: CellId) => void
  onMouseEnter: (cell: CellId) => void
}

/**
 * A single grid cell
 */
function GridCell({
  day,
  slot,
  isSelected,
  isHourMark,
  disabled,
  isDragging,
  onClick,
  onMouseDown,
  onMouseEnter,
}: GridCellProps) {
  const cell: CellId = { day, slot }

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    if (!isDragging) {
      onClick(cell)
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    onMouseDown(cell)
  }

  const handleMouseEnter = () => {
    if (isDragging) {
      onMouseEnter(cell)
    }
  }

  return (
    <button
      type="button"
      className={`
        border-border
        ${isHourMark ? 'border-l' : 'border-l-0'}
        border-t border-r-0 border-b
        transition-colors
        ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}
        ${isSelected ? 'bg-primary hover:bg-primary/90' : 'bg-background hover:bg-accent'}
      `}
      style={{ width: '15px', height: '24px' }}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseEnter={handleMouseEnter}
      disabled={disabled}
      aria-label={`${DAY_LABELS[day]} ${slotToTime(slot)}`}
      aria-pressed={isSelected}
    />
  )
}
