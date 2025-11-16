import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminRoute } from './components/AdminRoute'
import { BackendAuthProvider } from './contexts/BackendAuthContext'
import {
  BackendAvailabilityProvider,
  useBackendAvailability,
} from './contexts/BackendAvailabilityContext'
import { useAuth } from './hooks/useAuth'
import { setAccessTokenGetter } from './lib/api'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Dashboard from './pages/Dashboard'
import { Contacts } from './pages/Contacts'
import { Routes as RoutesPage } from './pages/Routes'
import { RouteDetails } from './pages/RouteDetails'
import { CreateRoute } from './pages/CreateRoute'
import { ServiceUnavailable } from './pages/ServiceUnavailable'
import AdminUsers from './pages/admin/AdminUsers'

function AppRoutes() {
  const { isAvailable, isChecking, lastChecked, checkAvailability } = useBackendAvailability()

  // If backend is unavailable, show service unavailable page
  if (!isAvailable) {
    return (
      <ServiceUnavailable
        onRetry={checkAvailability}
        lastChecked={lastChecked ?? undefined}
        isRetrying={isChecking}
      />
    )
  }

  return (
    <BrowserRouter>
      <BackendAuthProvider>
        <AppLayout>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/login" element={<Login />} />
            <Route path="/callback" element={<Callback />} />

            {/* Protected routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/contacts"
              element={
                <ProtectedRoute>
                  <Contacts />
                </ProtectedRoute>
              }
            />
            <Route
              path="/routes"
              element={
                <ProtectedRoute>
                  <RoutesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/routes/new"
              element={
                <ProtectedRoute>
                  <CreateRoute />
                </ProtectedRoute>
              }
            />
            <Route
              path="/routes/:id"
              element={
                <ProtectedRoute>
                  <RouteDetails />
                </ProtectedRoute>
              }
            />

            {/* Admin routes */}
            <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
            <Route
              path="/admin/users"
              element={
                <AdminRoute>
                  <AdminUsers />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/analytics"
              element={
                <AdminRoute>
                  <div className="flex min-h-screen items-center justify-center">
                    <div className="text-center">
                      <h1 className="text-2xl font-bold">Admin Analytics</h1>
                      <p className="text-muted-foreground">Analytics dashboard (placeholder)</p>
                    </div>
                  </div>
                </AdminRoute>
              }
            />
            <Route
              path="/admin/logs"
              element={
                <AdminRoute>
                  <div className="flex min-h-screen items-center justify-center">
                    <div className="text-center">
                      <h1 className="text-2xl font-bold">Admin Logs</h1>
                      <p className="text-muted-foreground">
                        Notification logs viewer (placeholder)
                      </p>
                    </div>
                  </div>
                </AdminRoute>
              }
            />
            <Route
              path="/admin/actions"
              element={
                <AdminRoute>
                  <div className="flex min-h-screen items-center justify-center">
                    <div className="text-center">
                      <h1 className="text-2xl font-bold">Admin Actions</h1>
                      <p className="text-muted-foreground">
                        Administrative actions page (placeholder)
                      </p>
                    </div>
                  </div>
                </AdminRoute>
              }
            />

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AppLayout>
      </BackendAuthProvider>
    </BrowserRouter>
  )
}

function AppContent() {
  const { getAccessToken } = useAuth()

  // Set up the access token getter for the API client
  // This allows the API client to retrieve fresh tokens on each request
  // Note: No cleanup function - the access token getter should persist across
  // component remounts during navigation (e.g., Auth0 callback flow)
  useEffect(() => {
    setAccessTokenGetter(getAccessToken)
  }, [getAccessToken])

  return (
    <BackendAvailabilityProvider>
      <AppRoutes />
    </BackendAvailabilityProvider>
  )
}

function App() {
  return <AppContent />
}

export default App
