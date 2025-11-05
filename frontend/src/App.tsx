import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './hooks/useAuth'
import { setAccessTokenGetter } from './lib/api'
import Login from './pages/Login'
import Callback from './pages/Callback'
import Dashboard from './pages/Dashboard'
import { Contacts } from './pages/Contacts'

function App() {
  const { getAccessToken } = useAuth()

  // Set up the access token getter for the API client
  // This allows the API client to retrieve fresh tokens on each request
  // The cleanup function resets it on unmount to prevent stale references
  useEffect(() => {
    setAccessTokenGetter(getAccessToken)

    return () => {
      // Reset on unmount to prevent stale references
      setAccessTokenGetter(() => Promise.reject(new Error('Auth context unmounted')))
    }
  }, [getAccessToken])

  return (
    <BrowserRouter>
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

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  )
}

export default App
