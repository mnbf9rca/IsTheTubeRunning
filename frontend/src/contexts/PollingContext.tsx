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
  // Note: We don't dispose the coordinator here because in React StrictMode (development),
  // components mount → unmount → remount. Disposing on the first unmount would break
  // polling when the component remounts. The coordinator will be garbage collected
  // when the component is truly unmounted (not during StrictMode's intentional unmounts).
  useEffect(() => {
    return () => {
      // coordinator.dispose() - intentionally not disposing (see note above)
    }
  }, [coordinator])

  const registerPoll = useCallback(
    (options: PollingOptions) => {
      const cleanup = coordinator.register(options)

      // Immediately pause polls if registered while backend is down or user is logged out
      // This ensures polls respect current state at registration time
      if (!isAvailable && options.pauseWhenBackendDown !== false) {
        coordinator.pause(options.key)
      }
      if (!isBackendAuthenticated && options.requiresAuth) {
        coordinator.pause(options.key)
      }

      return cleanup
    },
    [coordinator, isAvailable, isBackendAuthenticated]
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
