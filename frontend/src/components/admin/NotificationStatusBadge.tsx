import { Badge } from '../ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip'
import type { NotificationStatus } from '@/lib/api'

interface NotificationStatusBadgeProps {
  status: NotificationStatus
}

/**
 * Badge component showing notification status (Sent/Failed/Pending) with tooltip
 *
 * Displays color-coded badge based on notification delivery status:
 * - Green: Sent successfully
 * - Red: Failed to send
 * - Yellow: Pending delivery
 *
 * Includes tooltip explaining each status.
 *
 * @param status - The notification status ('sent', 'failed', or 'pending')
 */
export function NotificationStatusBadge({ status }: NotificationStatusBadgeProps) {
  if (status === 'sent') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge
              variant="default"
              className="bg-green-600 hover:bg-green-700 font-normal cursor-help"
            >
              Sent
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>Notification was successfully delivered to the recipient.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  if (status === 'failed') {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge variant="destructive" className="font-normal cursor-help">
              Failed
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <p>Notification failed to send. Check error message for details.</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  // status === 'pending'
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="default"
            className="bg-yellow-600 hover:bg-yellow-700 font-normal cursor-help"
          >
            Pending
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>Notification is queued and awaiting delivery.</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
