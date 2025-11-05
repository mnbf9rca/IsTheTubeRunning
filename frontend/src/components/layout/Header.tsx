import { Link } from 'react-router-dom'
import { Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { useAuth } from '@/hooks/useAuth'
import { Navigation } from './Navigation'

export const Header = () => {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth()

  const getUserInitials = () => {
    if (!user) return '?'
    if (user.name) {
      const names = user.name.split(' ')
      return names
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    }
    return user.email?.[0].toUpperCase() || '?'
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <Link to="/" className="mr-8 flex items-center space-x-2">
          <span className="text-xl font-bold">TfL Alerts</span>
        </Link>

        {/* Desktop Navigation */}
        {isAuthenticated && (
          <div className="hidden md:flex flex-1">
            <Navigation />
          </div>
        )}

        {/* Right Side */}
        <div className="flex flex-1 items-center justify-end space-x-4">
          {isLoading ? (
            <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
          ) : isAuthenticated && user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="relative h-10 w-10 rounded-full">
                  <Avatar>
                    <AvatarImage src={user.picture} alt={user.name || user.email} />
                    <AvatarFallback>{getUserInitials()}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent className="w-56" align="end">
                <DropdownMenuLabel>
                  <div className="flex flex-col space-y-1">
                    {user.name && <p className="text-sm font-medium">{user.name}</p>}
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/dashboard">Dashboard</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/dashboard/contacts">Contacts</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={logout}>Log out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button onClick={login}>Log in</Button>
          )}

          {/* Mobile Menu */}
          {isAuthenticated && (
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-6 w-6" />
                  <span className="sr-only">Toggle menu</span>
                </Button>
              </SheetTrigger>
              <SheetContent side="right">
                <Navigation />
              </SheetContent>
            </Sheet>
          )}
        </div>
      </div>
    </header>
  )
}
