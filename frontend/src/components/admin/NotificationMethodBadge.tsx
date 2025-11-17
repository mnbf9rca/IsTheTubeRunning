import { Mail, MessageSquare } from 'lucide-react'
import { Badge } from '../ui/badge'
import type { NotificationMethod } from '@/lib/api'

interface NotificationMethodBadgeProps {
  method: NotificationMethod
}

/**
 * Badge component showing notification method (Email/SMS) with icon
 *
 * Displays color-coded badge with icon based on notification method:
 * - Blue with Mail icon: Email notifications
 * - Purple with MessageSquare icon: SMS notifications
 *
 * @param method - The notification method ('email' or 'sms')
 */
export function NotificationMethodBadge({ method }: NotificationMethodBadgeProps) {
  if (method === 'email') {
    return (
      <Badge variant="default" className="bg-blue-600 hover:bg-blue-700 font-normal gap-1">
        <Mail className="h-3 w-3" />
        Email
      </Badge>
    )
  }

  // method === 'sms'
  return (
    <Badge variant="default" className="bg-purple-600 hover:bg-purple-700 font-normal gap-1">
      <MessageSquare className="h-3 w-3" />
      SMS
    </Badge>
  )
}
