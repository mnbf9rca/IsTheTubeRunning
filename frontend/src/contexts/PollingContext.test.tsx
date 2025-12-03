/* eslint-disable react-hooks/globals */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PollingProvider, usePollingCoordinator } from './PollingContext'
import type { PollingCoordinator } from '@/lib/PollingCoordinator'
import * as BackendAvailabilityHook from '@/hooks/useBackendAvailability'
import * as BackendAuthHook from '@/hooks/useBackendAuth'

// Mock the hooks
vi.mock('@/hooks/useBackendAvailability')
vi.mock('@/hooks/useBackendAuth')

describe('PollingContext', () => {
  const mockUseBackendAvailability = vi.mocked(BackendAvailabilityHook.useBackendAvailability)
  const mockUseBackendAuth = vi.mocked(BackendAuthHook.useBackendAuth)

  beforeEach(() => {
    vi.useFakeTimers()

    // Default mocks
    mockUseBackendAvailability.mockReturnValue({
      isAvailable: true,
      isChecking: false,
      lastChecked: new Date(),
      checkAvailability: vi.fn(),
    })

    mockUseBackendAuth.mockReturnValue({
      isBackendAuthenticated: true,
      loading: false,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  describe('PollingProvider', () => {
    it('should provide polling coordinator to children', () => {
      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        return <div>Has Coordinator: {coordinator ? 'Yes' : 'No'}</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      expect(screen.getByText('Has Coordinator: Yes')).toBeInTheDocument()
    })

    it('should provide registerPoll function', () => {
      function TestComponent() {
        const { registerPoll } = usePollingCoordinator()
        return <div>Has Register: {registerPoll ? 'Yes' : 'No'}</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      expect(screen.getByText('Has Register: Yes')).toBeInTheDocument()
    })

    it('should initialize coordinator with focus listener', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Coordinator should be initialized
      expect(capturedCoordinator).not.toBeNull()

      // Focus listener should be set up
      const spy = vi.fn()
      capturedCoordinator!.register({
        key: 'test',
        callback: spy,
        interval: 10000,
      })

      // Wait for initial stagger delay and clear the call
      await vi.advanceTimersByTimeAsync(0)
      spy.mockClear()

      // Trigger window focus event
      window.dispatchEvent(new Event('focus'))

      // Should trigger callback with 0ms stagger
      await vi.advanceTimersByTimeAsync(0)
      expect(spy).toHaveBeenCalledTimes(1)
    })

    it('should allow multiple children to access coordinator', () => {
      function ChildComponent({ id }: { id: string }) {
        const { coordinator } = usePollingCoordinator()
        return (
          <div>
            Child {id}: {coordinator ? 'Yes' : 'No'}
          </div>
        )
      }

      function ParentComponent() {
        return (
          <div>
            <ChildComponent id="1" />
            <ChildComponent id="2" />
          </div>
        )
      }

      render(
        <PollingProvider>
          <ParentComponent />
        </PollingProvider>
      )

      expect(screen.getByText('Child 1: Yes')).toBeInTheDocument()
      expect(screen.getByText('Child 2: Yes')).toBeInTheDocument()
    })

    it('should cleanup coordinator on unmount', () => {
      let capturedCoordinator: PollingCoordinator | null = null

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { unmount } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register a poll
      const spy = vi.fn()
      capturedCoordinator!.register({
        key: 'test',
        callback: spy,
        interval: 10000,
      })

      // Unmount
      unmount()

      // Advance time - callback should not be called
      vi.advanceTimersByTime(10000)
      expect(spy).not.toHaveBeenCalled()
    })
  })

  describe('registerPoll', () => {
    it('should register poll with coordinator', () => {
      let capturedCoordinator: PollingCoordinator | null = null

      function TestComponent() {
        const { coordinator, registerPoll } = usePollingCoordinator()
        capturedCoordinator = coordinator

        // Register a poll
        const callback = vi.fn()
        registerPoll({
          key: 'test-poll',
          callback,
          interval: 10000,
        })

        return <div>Test</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Verify poll was registered
      expect(capturedCoordinator!.getRegisteredPolls()).toContain('test-poll')
    })

    it('should return cleanup function', () => {
      let cleanup: (() => void) | null = null

      function TestComponent() {
        const { registerPoll } = usePollingCoordinator()

        cleanup = registerPoll({
          key: 'test-poll',
          callback: vi.fn(),
          interval: 10000,
        })

        return <div>Test</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      expect(cleanup).toBeInstanceOf(Function)
    })
  })

  describe('backend availability changes', () => {
    it('should pause health-aware polls when backend goes down', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with backend available
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: true,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register a health-aware poll
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'health-aware',
        callback,
        interval: 10000,
        pauseWhenBackendDown: true,
      })

      // Advance to first execution
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      // Backend goes down
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: false,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Advance time - callback should not be called again
      await vi.advanceTimersByTimeAsync(10000)
      expect(callback).toHaveBeenCalledTimes(1) // Still just the initial call

      // Verify poll is paused
      const status = capturedCoordinator!.getPollStatus('health-aware')
      expect(status?.isPaused).toBe(true)
    })

    it('should resume health-aware polls with jitter when backend comes back up', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with backend down
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: false,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register a health-aware poll while backend is down
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'health-aware',
        callback,
        interval: 10000,
        pauseWhenBackendDown: true,
      })

      // Backend comes back up
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: true,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Should resume with jitter (0-5000ms delay)
      // Let's advance to the maximum jitter time
      await vi.advanceTimersByTimeAsync(5000)

      // Callback should have been called at least once
      expect(callback).toHaveBeenCalled()
    })

    it('should not pause non-health-aware polls when backend goes down', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with backend available
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: true,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register a non-health-aware poll
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'non-health-aware',
        callback,
        interval: 10000,
        pauseWhenBackendDown: false,
      })

      // Advance to first execution
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      // Backend goes down
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: false,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Advance time - callback should still be called
      await vi.advanceTimersByTimeAsync(10000)
      expect(callback).toHaveBeenCalledTimes(2)

      // Verify poll is not paused
      const status = capturedCoordinator!.getPollStatus('non-health-aware')
      expect(status?.isPaused).toBe(false)
    })
  })

  describe('authentication changes', () => {
    it('should pause authenticated polls when user logs out', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with user authenticated
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: true,
        loading: false,
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register an authenticated poll
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'auth-poll',
        callback,
        interval: 10000,
        requiresAuth: true,
      })

      // Advance to first execution
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      // User logs out
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: false,
        loading: false,
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Advance time - callback should not be called again
      await vi.advanceTimersByTimeAsync(10000)
      expect(callback).toHaveBeenCalledTimes(1) // Still just the initial call

      // Verify poll is paused
      const status = capturedCoordinator!.getPollStatus('auth-poll')
      expect(status?.isPaused).toBe(true)
    })

    it('should resume authenticated polls when user logs in', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with user not authenticated
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: false,
        loading: false,
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register an authenticated poll while logged out
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'auth-poll',
        callback,
        interval: 10000,
        requiresAuth: true,
      })

      // User logs in
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: true,
        loading: false,
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Should resume immediately (no jitter for auth changes)
      await vi.advanceTimersByTimeAsync(0)

      // Callback should have been called
      expect(callback).toHaveBeenCalled()
    })

    it('should not pause non-authenticated polls when user logs out', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with user authenticated
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: true,
        loading: false,
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register a non-authenticated poll
      const callback = vi.fn()
      capturedCoordinator!.register({
        key: 'public-poll',
        callback,
        interval: 10000,
        requiresAuth: false,
      })

      // Advance to first execution
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      // User logs out
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: false,
        loading: false,
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Advance time - callback should still be called
      await vi.advanceTimersByTimeAsync(10000)
      expect(callback).toHaveBeenCalledTimes(2)

      // Verify poll is not paused
      const status = capturedCoordinator!.getPollStatus('public-poll')
      expect(status?.isPaused).toBe(false)
    })
  })

  describe('usePollingCoordinator', () => {
    it('should throw error when used outside PollingProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      function TestComponent() {
        usePollingCoordinator() // This should throw
        return <div>Should not render</div>
      }

      expect(() => {
        render(<TestComponent />)
      }).toThrow('usePollingCoordinator must be used within a PollingProvider')

      consoleSpy.mockRestore()
    })

    it('should return coordinator and registerPoll when used within PollingProvider', () => {
      let capturedContext: { coordinator: PollingCoordinator; registerPoll: unknown } | null = null

      function TestComponent() {
        const context = usePollingCoordinator()
        capturedContext = context
        return <div>Test</div>
      }

      render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      expect(capturedContext).not.toBeNull()
      expect(capturedContext!.coordinator).toBeDefined()
      expect(capturedContext!.registerPoll).toBeInstanceOf(Function)
    })

    it('should return same coordinator on re-renders', () => {
      const coordinators: PollingCoordinator[] = []

      function TestComponent({ counter }: { counter: number }) {
        const { coordinator } = usePollingCoordinator()
        coordinators.push(coordinator)
        return <div>{counter}</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent counter={1} />
        </PollingProvider>
      )

      rerender(
        <PollingProvider>
          <TestComponent counter={2} />
        </PollingProvider>
      )

      expect(coordinators).toHaveLength(2)
      expect(coordinators[0]).toBe(coordinators[1]) // Same reference
    })
  })

  describe('combined availability and auth changes', () => {
    it('should handle both backend down and user logout', async () => {
      let capturedCoordinator: PollingCoordinator | null = null

      // Start with backend available and user authenticated
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: true,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: true,
        loading: false,
      })

      function TestComponent() {
        const { coordinator } = usePollingCoordinator()
        capturedCoordinator = coordinator
        return <div>Test</div>
      }

      const { rerender } = render(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // Register polls
      const authCallback = vi.fn()
      const healthCallback = vi.fn()
      const bothCallback = vi.fn()

      capturedCoordinator!.register({
        key: 'auth-only',
        callback: authCallback,
        interval: 10000,
        requiresAuth: true,
        pauseWhenBackendDown: false,
      })

      capturedCoordinator!.register({
        key: 'health-only',
        callback: healthCallback,
        interval: 10000,
        requiresAuth: false,
        pauseWhenBackendDown: true,
      })

      capturedCoordinator!.register({
        key: 'both',
        callback: bothCallback,
        interval: 10000,
        requiresAuth: true,
        pauseWhenBackendDown: true,
      })

      // Advance to first execution (accounting for stagger delays: 0ms, 1000ms, 2000ms)
      await vi.advanceTimersByTimeAsync(3000)
      expect(authCallback).toHaveBeenCalledTimes(1)
      expect(healthCallback).toHaveBeenCalledTimes(1)
      expect(bothCallback).toHaveBeenCalledTimes(1)

      // Backend goes down
      mockUseBackendAvailability.mockReturnValue({
        isAvailable: false,
        isChecking: false,
        lastChecked: new Date(),
        checkAvailability: vi.fn(),
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // health-only and both should be paused
      expect(capturedCoordinator!.getPollStatus('health-only')?.isPaused).toBe(true)
      expect(capturedCoordinator!.getPollStatus('both')?.isPaused).toBe(true)
      expect(capturedCoordinator!.getPollStatus('auth-only')?.isPaused).toBe(false)

      // User logs out
      mockUseBackendAuth.mockReturnValue({
        isBackendAuthenticated: false,
        loading: false,
      })

      rerender(
        <PollingProvider>
          <TestComponent />
        </PollingProvider>
      )

      // All polls with auth requirement should be paused
      expect(capturedCoordinator!.getPollStatus('auth-only')?.isPaused).toBe(true)
      expect(capturedCoordinator!.getPollStatus('both')?.isPaused).toBe(true)
      expect(capturedCoordinator!.getPollStatus('health-only')?.isPaused).toBe(true)
    })
  })
})
