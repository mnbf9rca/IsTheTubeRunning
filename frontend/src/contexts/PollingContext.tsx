import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { PollingCoordinator } from '@/lib/PollingCoordinator'
import type { PollingOptions } from '@/lib/PollingCoordinator'
import { useBackendAvailability } from '@/hooks/useBackendAvailability'
import { useBackendAuth } from '@/hooks/useBackendAuth'

export interface PollingContextType {
  coordinator: PollingCoordinator
  registerPoll: (options: PollingOptions) => () => void
}

const PollingContext = createContext<PollingContextType | undefined>(undefined)

export function PollingProvider({ children }: { children: ReactNode }) {
  const { isAvailable } = useBackendAvailability()
  const { isBackendAuthenticated } = useBackendAuth()

  // Initialize coordinator once with lazy initializer
  const [coordinator] = useState(() => {
    const coord = new PollingCoordinator()
    coord.setupWindowFocusListener()
    return coord
  })

  // Track previous states to detect changes
  const prevIsAvailable = useRef(isAvailable)
  const prevIsAuthenticated = useRef(isBackendAuthenticated)

  // Initial state: pause polls if backend is already down or user is already logged out
  // This prevents polls from starting when registered in an unavailable/unauthenticated state
  useEffect(() => {
    if (!isAvailable) {
      coordinator.pauseHealthAwarePolls()
    }
    if (!isBackendAuthenticated) {
      coordinator.pauseAuthenticatedPolls()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run once on mount

  // Handle backend availability changes
  useEffect(() => {
    const wasAvailable = prevIsAvailable.current
    const isNowAvailable = isAvailable

    if (wasAvailable && !isNowAvailable) {
      // Backend went down - pause health-aware polls
      coordinator.pauseHealthAwarePolls()
    } else if (!wasAvailable && isNowAvailable) {
      // Backend came back up - resume with jitter to prevent thundering herd
      coordinator.resumeHealthAwarePolls(true)
    }

    prevIsAvailable.current = isAvailable
  }, [isAvailable, coordinator])

  // Handle authentication changes
  useEffect(() => {
    const wasAuthenticated = prevIsAuthenticated.current
    const isNowAuthenticated = isBackendAuthenticated

    if (wasAuthenticated && !isNowAuthenticated) {
      // User logged out - pause authenticated polls
      coordinator.pauseAuthenticatedPolls()
    } else if (!wasAuthenticated && isNowAuthenticated) {
      // User logged in - resume authenticated polls
      coordinator.resumeAuthenticatedPolls()
    }

    prevIsAuthenticated.current = isBackendAuthenticated
  }, [isBackendAuthenticated, coordinator])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      coordinator.dispose()
    }
  }, [coordinator])

  const registerPoll = useCallback(
    (options: PollingOptions) => {
      return coordinator.register(options)
    },
    [coordinator]
  )

  const contextValue = useMemo(() => ({ coordinator, registerPoll }), [coordinator, registerPoll])

  return <PollingContext.Provider value={contextValue}>{children}</PollingContext.Provider>
}

export function usePollingCoordinator(): PollingContextType {
  const context = useContext(PollingContext)
  if (context === undefined) {
    throw new Error('usePollingCoordinator must be used within a PollingProvider')
  }
  return context
}
