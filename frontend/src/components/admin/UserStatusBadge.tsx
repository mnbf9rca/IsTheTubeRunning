import { Badge } from '../ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'

interface UserStatusBadgeProps {
  deletedAt: string | null
}

/**
 * Badge component showing user status (Active/Deleted) with tooltip
 *
 * Displays a green "Active" badge for active users (deletedAt is null)
 * or a red "Deleted" badge for anonymized users (deletedAt is set).
 * Includes a tooltip explaining what each status means.
 *
 * @param deletedAt - Timestamp when user was deleted/anonymized, or null if active
 */
export function UserStatusBadge({ deletedAt }: UserStatusBadgeProps) {
  if (deletedAt) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="destructive" className="font-normal cursor-help">
              Deleted
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>User has been anonymized. All personal data (emails, phones) removed.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="default"
            className="bg-green-600 hover:bg-green-700 font-normal cursor-help"
          >
            Active
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>User is active and can use the system normally.</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
