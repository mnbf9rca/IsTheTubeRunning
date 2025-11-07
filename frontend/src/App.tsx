import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
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
import { ServiceUnavailable } from './pages/ServiceUnavailable'

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
