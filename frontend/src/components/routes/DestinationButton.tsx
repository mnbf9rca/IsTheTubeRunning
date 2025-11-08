import { Check } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface DestinationButtonProps {
  onClick: () => void
  disabled?: boolean
}

/**
 * DestinationButton component for marking a station as the journey destination
 *
 * When clicked, adds the current station as the final segment with line_tfl_id: null
 */
export function DestinationButton({ onClick, disabled = false }: DestinationButtonProps) {
  return (
    <Button
      type="button"
      variant="outline"
      onClick={onClick}
      disabled={disabled}
      className="gap-2"
      aria-label="Mark this as my destination"
    >
      <Check className="h-4 w-4" aria-hidden="true" />
      This is my destination
    </Button>
  )
}
