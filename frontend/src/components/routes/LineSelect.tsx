import { Badge } from '../ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import type { LineResponse } from '@/types'
import { getLineColor } from '@/lib/tfl-colors'

export interface LineSelectProps {
  /**
   * Array of available lines
   */
  lines: LineResponse[]

  /**
   * Currently selected line ID (UUID, not TfL ID)
   */
  value: string | undefined

  /**
   * Callback when selection changes
   */
  onChange: (lineId: string) => void

  /**
   * Placeholder text when no line selected
   */
  placeholder?: string

  /**
   * Whether the select is disabled
   */
  disabled?: boolean

  /**
   * ARIA label for accessibility
   */
  'aria-label'?: string
}

/**
 * Line selector component with color indicator
 *
 * Displays a searchable dropdown of TfL lines with color badges.
 *
 * @example
 * <LineSelect
 *   lines={lines}
 *   value={selectedLineId}
 *   onChange={setSelectedLineId}
 *   placeholder="Select a line"
 * />
 */
export function LineSelect({
  lines,
  value,
  onChange,
  placeholder = 'Select a line',
  disabled = false,
  'aria-label': ariaLabel = 'Select tube line',
}: LineSelectProps) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger aria-label={ariaLabel}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {lines.map((line) => (
          <SelectItem key={line.id} value={line.id}>
            <div className="flex items-center gap-2">
              <Badge
                style={{ backgroundColor: getLineColor(line.tfl_id) }}
                className="h-4 w-4 rounded-full p-0"
                aria-label={`${line.name} line color`}
              />
              <span>{line.name}</span>
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
