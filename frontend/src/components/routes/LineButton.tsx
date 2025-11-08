import { Train } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getLineTextColor, getLineColor } from '@/lib/tfl-colors'
import type { LineResponse } from '@/lib/api'
import { cn } from '@/lib/utils'

interface LineButtonProps {
  line: LineResponse
  selected?: boolean
  onClick: () => void
  size?: 'sm' | 'md' | 'lg'
}

/**
 * LineButton component for TfL line selection
 *
 * Displays a line as a colored button following TfL brand guidelines:
 * - Background: line color
 * - Text: white for most lines, Corporate Blue for Circle/H&C/W&C
 * - Icon: Subway (🚇)
 */
export function LineButton({ line, selected = false, onClick, size = 'md' }: LineButtonProps) {
  const textColor = getLineTextColor(line.tfl_id)
  const backgroundColor = getLineColor(line.tfl_id)

  // Size variants
  const sizeClasses = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-10 px-4 text-base',
    lg: 'h-12 px-5 text-lg',
  }

  return (
    <Button
      type="button"
      onClick={onClick}
      className={cn(
        'font-medium transition-all gap-2',
        sizeClasses[size],
        // Selected state: add border and slight shadow
        selected && 'ring-2 ring-offset-2 ring-primary',
        // Hover state
        'hover:opacity-90'
      )}
      style={{
        backgroundColor,
        color: textColor,
      }}
      aria-label={`Travel on ${line.name} line`}
      aria-pressed={selected}
    >
      <Train className="h-4 w-4" aria-hidden="true" />
      {line.name}
    </Button>
  )
}
