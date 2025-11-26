import { createContext, useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { useConfig } from './ConfigContext'

interface BackendAvailabilityContextType {
  isAvailable: boolean
  isChecking: boolean
  lastChecked: Date | null
  checkAvailability: () => Promise<void>
}

const BackendAvailabilityContext = createContext<BackendAvailabilityContextType | undefined>(
  undefined
)

// Export context for use in hooks
export { BackendAvailabilityContext }

const CHECK_INTERVAL_MS = 10000 // 10 seconds

export function BackendAvailabilityProvider({ children }: { children: ReactNode }) {
  const config = useConfig()
  const [isAvailable, setIsAvailable] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const checkAvailability = useCallback(async () => {
    setIsChecking(true)
    try {
      // Extract protocol and host using URL API for robust URL construction
      const baseUrl = new URL(config.api.baseUrl)
      const apiBaseUrl = `${baseUrl.protocol}//${baseUrl.host}`
      const response = await fetch(`${apiBaseUrl}/api/v1/auth/ready`, {
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
  }, [config])

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

// Re-export hook for backward compatibility
// eslint-disable-next-line react-refresh/only-export-components
export { useBackendAvailability } from '@/hooks/useBackendAvailability'
