import { Bell, Mail, Smartphone } from 'lucide-react'
import { Badge } from '../ui/badge'
import { Card } from '../ui/card'
import type { NotificationPreferenceResponse, EmailResponse, PhoneResponse } from '@/types'

export interface NotificationDisplayProps {
  /**
   * Array of notification preferences to display
   */
  preferences: NotificationPreferenceResponse[]

  /**
   * Array of email contacts (for looking up email details)
   */
  emails: EmailResponse[]

  /**
   * Array of phone contacts (for looking up phone details)
   */
  phones: PhoneResponse[]
}

/**
 * Display a read-only list of notification preferences
 *
 * Shows where alerts will be sent (email addresses or phone numbers) for a route.
 * This is the read-only version without delete buttons.
 *
 * @example
 * <NotificationDisplay
 *   preferences={route.notification_preferences}
 *   emails={contacts.emails}
 *   phones={contacts.phones}
 * />
 */
export function NotificationDisplay({ preferences, emails, phones }: NotificationDisplayProps) {
  if (preferences.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <Bell className="mb-3 h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">
          No notification methods configured. Alerts won't be sent for this route.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {preferences.map((preference) => {
        // Find the contact details
        let contactText = 'Unknown contact'
        let icon: React.ReactNode = <Bell className="h-4 w-4" />

        if (preference.method === 'email' && preference.target_email_id) {
          const email = emails.find((e) => e.id === preference.target_email_id)
          if (email) {
            contactText = email.email
            icon = <Mail className="h-4 w-4" />
          }
        } else if (preference.method === 'sms' && preference.target_phone_id) {
          const phone = phones.find((p) => p.id === preference.target_phone_id)
          if (phone) {
            contactText = phone.phone
            icon = <Smartphone className="h-4 w-4" />
          }
        }

        return (
          <Card key={preference.id} className="flex items-center gap-3 p-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
              {icon}
            </div>
            <div className="flex-1">
              <div className="font-medium">{contactText}</div>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="secondary" className="text-xs">
                  {preference.method.toUpperCase()}
                </Badge>
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}
