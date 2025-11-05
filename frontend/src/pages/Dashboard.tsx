import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { MapPin, Bell, Contact } from 'lucide-react'

export default function Dashboard() {
  const { user } = useAuth()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Welcome back{user?.name ? `, ${user.name.split(' ')[0]}` : ''}!
        </h1>
        <p className="text-muted-foreground">
          Manage your routes and stay informed about tube disruptions
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Routes</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">No routes configured yet</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contacts</CardTitle>
            <Contact className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">No contacts added yet</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Alerts</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-xs text-muted-foreground">No active alerts</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting Started</CardTitle>
          <CardDescription>Follow these steps to set up your alert system</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start space-x-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
              1
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Add your contacts</p>
              <p className="text-sm text-muted-foreground">
                Add and verify your email addresses and phone numbers to receive alerts
              </p>
            </div>
          </div>
          <div className="flex items-start space-x-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              2
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Create your routes</p>
              <p className="text-sm text-muted-foreground">
                Define your commute routes with stations and interchanges
              </p>
            </div>
          </div>
          <div className="flex items-start space-x-4">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              3
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Configure notifications</p>
              <p className="text-sm text-muted-foreground">
                Set up when and how you want to be notified about disruptions
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
