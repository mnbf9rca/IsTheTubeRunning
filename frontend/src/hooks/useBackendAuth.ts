import { useContext } from 'react'
import { BackendAuthContext } from '@/contexts/BackendAuthContext'

export function useBackendAuth() {
  const context = useContext(BackendAuthContext)
  if (context === undefined) {
    throw new Error('useBackendAuth must be used within a BackendAuthProvider')
  }
  return context
}
