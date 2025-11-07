import { Link, useLocation } from 'react-router-dom'
import { Home, MapPin, Bell, Contact } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  {
    title: 'Dashboard',
    href: '/dashboard',
    icon: Home,
  },
  {
    title: 'Routes',
    href: '/routes',
    icon: MapPin,
  },
  {
    title: 'Contacts',
    href: '/dashboard/contacts',
    icon: Contact,
  },
  {
    title: 'Alerts',
    href: '/dashboard',
    icon: Bell,
  },
]

export const Navigation = () => {
  const location = useLocation()

  return (
    <nav className="flex flex-col space-y-2 md:flex-row md:space-y-0 md:space-x-6">
      {navItems.map((item) => {
        const Icon = item.icon
        const isActive = location.pathname === item.href
        return (
          <Link
            key={item.title}
            to={item.href}
            className={cn(
              'flex items-center space-x-2 text-sm font-medium transition-colors hover:text-primary',
              isActive ? 'text-primary' : 'text-muted-foreground'
            )}
          >
            <Icon className="h-4 w-4" />
            <span>{item.title}</span>
          </Link>
        )
      })}
    </nav>
  )
}
