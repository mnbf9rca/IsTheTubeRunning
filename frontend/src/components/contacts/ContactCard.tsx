import { Mail, Phone, Trash2, CheckCircle2, AlertCircle } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import type { EmailResponse, PhoneResponse } from '../../lib/api'

export interface ContactCardProps {
  contact: EmailResponse | PhoneResponse
  type: 'email' | 'phone'
  onVerify: (id: string) => void
  onDelete: (id: string) => void
  isVerifying?: boolean
  isDeleting?: boolean
}

/**
 * ContactCard component displays a single contact (email or phone) with actions
 *
 * @param contact - The contact data (email or phone)
 * @param type - Type of contact ('email' or 'phone')
 * @param onVerify - Callback when verify button is clicked
 * @param onDelete - Callback when delete button is clicked
 * @param isVerifying - Loading state for verification
 * @param isDeleting - Loading state for deletion
 */
export function ContactCard({
  contact,
  type,
  onVerify,
  onDelete,
  isVerifying = false,
  isDeleting = false,
}: ContactCardProps) {
  const value = 'email' in contact ? contact.email : contact.phone
  const Icon = type === 'email' ? Mail : Phone

  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <Icon className="h-5 w-5 text-muted-foreground flex-shrink-0" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate" title={value}>
              {value}
            </p>
            <div className="flex gap-2 mt-1 flex-wrap">
              {contact.verified ? (
                <Badge variant="default" className="bg-green-500 hover:bg-green-600">
                  <CheckCircle2 className="h-3 w-3 mr-1" aria-hidden="true" />
                  Verified
                </Badge>
              ) : (
                <Badge variant="secondary">
                  <AlertCircle className="h-3 w-3 mr-1" aria-hidden="true" />
                  Unverified
                </Badge>
              )}
              {contact.is_primary && <Badge variant="outline">Primary</Badge>}
            </div>
          </div>
        </div>

        <div className="flex gap-2 ml-4 flex-shrink-0">
          {!contact.verified && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onVerify(contact.id)}
              disabled={isVerifying || isDeleting}
              aria-label={`Verify ${type}`}
            >
              {isVerifying ? 'Verifying...' : 'Verify'}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDelete(contact.id)}
            disabled={isVerifying || isDeleting}
            aria-label={`Delete ${type}`}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
