import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'

interface BackendAvailabilityContextType {
  isAvailable: boolean
  isChecking: boolean
  lastChecked: Date | null
  checkAvailability: () => Promise<void>
}

const BackendAvailabilityContext = createContext<BackendAvailabilityContextType | undefined>(
  undefined
)

const CHECK_INTERVAL_MS = 10000 // 10 seconds

export function BackendAvailabilityProvider({ children }: { children: ReactNode }) {
  const [isAvailable, setIsAvailable] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const checkAvailability = useCallback(async () => {
    setIsChecking(true)
    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/v1/auth/ready`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const data = await response.json()
        setIsAvailable(data.ready === true)
      } else {
        setIsAvailable(false)
      }
    } catch (error) {
      // Network error or backend down
      console.error('Backend availability check failed:', error)
      setIsAvailable(false)
    } finally {
      setLastChecked(new Date())
      setIsChecking(false)
    }
  }, [])

  // Check on mount
  useEffect(() => {
    checkAvailability()
  }, [checkAvailability])

  // Periodic checks
  useEffect(() => {
    const interval = setInterval(checkAvailability, CHECK_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [checkAvailability])

  // Re-check when window regains focus
  useEffect(() => {
    const handleFocus = () => {
      checkAvailability()
    }

    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [checkAvailability])

  return (
    <BackendAvailabilityContext.Provider
      value={{
        isAvailable,
        isChecking,
        lastChecked,
        checkAvailability,
      }}
    >
      {children}
    </BackendAvailabilityContext.Provider>
  )
}

export function useBackendAvailability() {
  const context = useContext(BackendAvailabilityContext)
  if (context === undefined) {
    throw new Error('useBackendAvailability must be used within a BackendAvailabilityProvider')
  }
  return context
}
