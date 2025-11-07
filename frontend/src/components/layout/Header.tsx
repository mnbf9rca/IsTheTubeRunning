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
import { useBackendAuth } from '@/contexts/BackendAuthContext'
import { resetAccessTokenGetter } from '@/lib/api'
import { Navigation } from './Navigation'

export const Header = () => {
  const { user, isLoading, login, logout } = useAuth()
  const { isBackendAuthenticated } = useBackendAuth()

  /**
   * Handle logout - cleans up auth state and resets API token getter
   */
  const handleLogout = () => {
    resetAccessTokenGetter()
    logout()
  }

  /**
   * Get user initials from name or email
   *
   * Handles edge cases:
   * - Multiple spaces between names
   * - Single-word names (returns first 2 chars)
   * - Empty or whitespace-only names
   * - Non-ASCII characters
   *
   * @returns 1-2 character string for avatar display
   */
  const getUserInitials = () => {
    if (!user) return '?'

    if (user.name) {
      // Split by whitespace and filter out empty strings
      const names = user.name.trim().split(/\s+/).filter(Boolean)

      if (names.length === 0) {
        // Name is empty or only whitespace, fall through to email
      } else if (names.length === 1) {
        // Single word name - return first 2 characters
        return names[0].slice(0, 2).toUpperCase()
      } else {
        // Multiple words - return first char of first 2 words
        return names
          .slice(0, 2)
          .map((n) => n[0])
          .join('')
          .toUpperCase()
      }
    }

    // Fallback to email first character
    return user.email?.[0]?.toUpperCase() || '?'
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <Link to="/" className="mr-8 flex items-center space-x-2">
          <span className="text-xl font-bold">TfL Alerts</span>
        </Link>

        {/* Desktop Navigation */}
        {isBackendAuthenticated && (
          <div className="hidden md:flex flex-1">
            <Navigation />
          </div>
        )}

        {/* Right Side */}
        <div className="flex flex-1 items-center justify-end space-x-4">
          {isLoading ? (
            <div className="h-8 w-8 animate-pulse rounded-full bg-muted" />
          ) : isBackendAuthenticated && user ? (
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
                <DropdownMenuItem onClick={handleLogout}>Log out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button onClick={login}>Log in</Button>
          )}

          {/* Mobile Menu */}
          {isBackendAuthenticated && (
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
