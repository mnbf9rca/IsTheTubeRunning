import { useState } from 'react'
import { ArrowLeftRight, Check, ChevronsUpDown } from 'lucide-react'
import { Button } from '../ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '../ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover'
import { cn } from '../../lib/utils'
import type { StationResponse } from '../../lib/api'

export interface StationComboboxProps {
  /**
   * Array of available stations
   */
  stations: StationResponse[]

  /**
   * Currently selected station ID (UUID, not TfL ID)
   */
  value: string | undefined

  /**
   * Callback when selection changes
   */
  onChange: (stationId: string) => void

  /**
   * Placeholder text when no station selected
   */
  placeholder?: string

  /**
   * Whether the combobox is disabled
   */
  disabled?: boolean

  /**
   * ARIA label for accessibility
   */
  'aria-label'?: string
}

/**
 * Searchable station selector component
 *
 * Displays a searchable dropdown of TfL stations using Command component.
 * Users can type to filter stations by name.
 *
 * @example
 * <StationCombobox
 *   stations={stations}
 *   value={selectedStationId}
 *   onChange={setSelectedStationId}
 *   placeholder="Select a station"
 * />
 */
export function StationCombobox({
  stations,
  value,
  onChange,
  placeholder = 'Select a station',
  disabled = false,
  'aria-label': ariaLabel = 'Select tube station',
}: StationComboboxProps) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  // Sort stations alphabetically
  const sortedStations = [...stations].sort((a, b) => a.name.localeCompare(b.name))

  // Filter stations by substring match (case-insensitive)
  const filteredStations = sortedStations.filter((station) =>
    station.name.toLowerCase().includes(search.toLowerCase())
  )

  // Find selected station for display
  const selectedStation = stations.find((station) => station.id === value)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={ariaLabel}
          disabled={disabled}
          className="w-full justify-between"
        >
          {selectedStation ? selectedStation.name : placeholder}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Search stations..." value={search} onValueChange={setSearch} />
          <CommandList>
            <CommandEmpty>No station found.</CommandEmpty>
            <CommandGroup>
              {filteredStations.map((station) => (
                <CommandItem
                  key={station.id}
                  value={station.name}
                  onSelect={() => {
                    onChange(station.id)
                    setOpen(false)
                    setSearch('') // Clear search on selection
                  }}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      value === station.id ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  <div className="flex items-center justify-between w-full">
                    <span>{station.name}</span>
                    {station.hub_naptan_code && (
                      <ArrowLeftRight
                        className="h-3 w-3 text-muted-foreground ml-2 shrink-0"
                        aria-label="Interchange station"
                      />
                    )}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
