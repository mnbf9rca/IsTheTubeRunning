import { useContext } from 'react'
import { BackendAvailabilityContext } from '@/contexts/BackendAvailabilityContext'

export function useBackendAvailability() {
  const context = useContext(BackendAvailabilityContext)
  if (context === undefined) {
    throw new Error('useBackendAvailability must be used within a BackendAvailabilityProvider')
  }
  return context
}
