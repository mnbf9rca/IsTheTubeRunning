import { Badge } from '../ui/badge'

interface UserStatusBadgeProps {
  deletedAt: string | null
}

/**
 * Badge component showing user status (Active/Deleted)
 *
 * Displays a green "Active" badge for active users (deletedAt is null)
 * or a red "Deleted" badge for anonymized users (deletedAt is set).
 *
 * @param deletedAt - Timestamp when user was deleted/anonymized, or null if active
 */
export function UserStatusBadge({ deletedAt }: UserStatusBadgeProps) {
  if (deletedAt) {
    return (
      <Badge variant="destructive" className="font-normal">
        Deleted
      </Badge>
    )
  }

  return (
    <Badge variant="default" className="bg-green-600 hover:bg-green-700 font-normal">
      Active
    </Badge>
  )
}
