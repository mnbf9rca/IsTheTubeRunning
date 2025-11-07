import { Calendar, Pencil, Trash2, Route as RouteIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import type { RouteListItemResponse } from '../../lib/api'

export interface RouteCardProps {
  route: RouteListItemResponse
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onClick?: (id: string) => void
  isDeleting?: boolean
}

/**
 * RouteCard component displays a single route with summary information and actions
 *
 * @param route - The route data
 * @param onEdit - Callback when edit button is clicked
 * @param onDelete - Callback when delete button is clicked
 * @param onClick - Optional callback when card is clicked (for navigation)
 * @param isDeleting - Loading state for deletion
 */
export function RouteCard({
  route,
  onEdit,
  onDelete,
  onClick,
  isDeleting = false,
}: RouteCardProps) {
  const handleCardClick = () => {
    if (onClick) {
      onClick(route.id)
    }
  }

  const handleEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    onEdit(route.id)
  }

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    onDelete(route.id)
  }

  return (
    <Card
      className={onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}
      onClick={handleCardClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-lg truncate" title={route.name}>
              {route.name}
            </CardTitle>
            {route.description && (
              <p
                className="text-sm text-muted-foreground mt-1 line-clamp-2"
                title={route.description}
              >
                {route.description}
              </p>
            )}
          </div>
          <Badge variant={route.active ? 'default' : 'secondary'} className="ml-2 flex-shrink-0">
            {route.active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="flex items-center gap-4 text-sm text-muted-foreground mb-4">
          <div className="flex items-center gap-1" title="Number of segments">
            <RouteIcon className="h-4 w-4" aria-hidden="true" />
            <span>{route.segment_count} segments</span>
          </div>
          <div className="flex items-center gap-1" title="Number of schedules">
            <Calendar className="h-4 w-4" aria-hidden="true" />
            <span>{route.schedule_count} schedules</span>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <Button
            size="sm"
            variant="outline"
            onClick={handleEdit}
            disabled={isDeleting}
            className="flex-1"
            aria-label={`Edit route ${route.name}`}
          >
            <Pencil className="h-4 w-4 mr-1" aria-hidden="true" />
            Edit
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleDelete}
            disabled={isDeleting}
            aria-label={`Delete route ${route.name}`}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
