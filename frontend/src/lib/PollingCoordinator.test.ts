import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { PollingCoordinator } from './PollingCoordinator'

describe('PollingCoordinator', () => {
  let coordinator: PollingCoordinator

  beforeEach(() => {
    vi.useFakeTimers()
    coordinator = new PollingCoordinator()
  })

  afterEach(() => {
    coordinator.dispose()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  describe('register', () => {
    it('should register a poll and return cleanup function', () => {
      const callback = vi.fn()
      const cleanup = coordinator.register({
        key: 'test-poll',
        callback,
        interval: 1000,
      })

      expect(typeof cleanup).toBe('function')
      expect(coordinator.getRegisteredPolls()).toContain('test-poll')
    })

    it('should execute callback with stagger delay on first run', async () => {
      const callback = vi.fn()

      coordinator.register({
        key: 'test-poll',
        callback,
        interval: 1000,
      })

      // Should not execute immediately
      expect(callback).not.toHaveBeenCalled()

      // Should execute after stagger delay (0ms for first poll)
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should stagger start times for multiple polls', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()
      const callback3 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 10000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 10000 })
      coordinator.register({ key: 'poll-3', callback: callback3, interval: 10000 })

      // Poll 1: 0ms delay
      await vi.advanceTimersByTimeAsync(0)
      expect(callback1).toHaveBeenCalledTimes(1)
      expect(callback2).not.toHaveBeenCalled()
      expect(callback3).not.toHaveBeenCalled()

      // Poll 2: 1000ms delay
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback2).toHaveBeenCalledTimes(1)
      expect(callback3).not.toHaveBeenCalled()

      // Poll 3: 2000ms delay
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback3).toHaveBeenCalledTimes(1)
    })

    it('should wrap stagger index after 5 polls', async () => {
      const callbacks = Array.from({ length: 6 }, () => vi.fn())

      callbacks.forEach((callback, i) => {
        coordinator.register({
          key: `poll-${i}`,
          callback,
          interval: 10000,
        })
      })

      // Poll 0: 0ms
      await vi.advanceTimersByTimeAsync(0)
      expect(callbacks[0]).toHaveBeenCalledTimes(1)

      // Polls 1-4: 1s, 2s, 3s, 4s
      await vi.advanceTimersByTimeAsync(4000)
      expect(callbacks[1]).toHaveBeenCalledTimes(1)
      expect(callbacks[4]).toHaveBeenCalledTimes(1)

      // Poll 5: should wrap back to 0ms (after 4s elapsed)
      await vi.advanceTimersByTimeAsync(0)
      expect(callbacks[5]).toHaveBeenCalledTimes(1)
    })

    it('should continue polling at specified interval', async () => {
      const callback = vi.fn()

      coordinator.register({
        key: 'test-poll',
        callback,
        interval: 1000,
      })

      // First execution (after stagger delay)
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      // Second execution (after interval)
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(2)

      // Third execution
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(3)
    })

    it('should handle async callbacks', async () => {
      const asyncCallback = vi.fn().mockResolvedValue('success')

      coordinator.register({
        key: 'async-poll',
        callback: asyncCallback,
        interval: 1000,
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(asyncCallback).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(1000)
      expect(asyncCallback).toHaveBeenCalledTimes(2)
    })

    it('should handle callback errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const callback = vi.fn().mockRejectedValue(new Error('Test error'))

      coordinator.register({
        key: 'error-poll',
        callback,
        interval: 1000,
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(consoleErrorSpy).toHaveBeenCalled()

      // Should continue polling despite error
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(2)

      consoleErrorSpy.mockRestore()
    })

    it('should replace existing poll with same key', () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      coordinator.register({ key: 'duplicate', callback: callback1, interval: 1000 })
      coordinator.register({ key: 'duplicate', callback: callback2, interval: 1000 })

      expect(consoleWarnSpy).toHaveBeenCalled()
      expect(coordinator.getRegisteredPolls()).toEqual(['duplicate'])

      consoleWarnSpy.mockRestore()
    })

    it('should not register after disposal', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      coordinator.dispose()

      const cleanup = coordinator.register({ key: 'test', callback: vi.fn(), interval: 1000 })

      expect(consoleWarnSpy).toHaveBeenCalled()
      expect(coordinator.getRegisteredPolls()).toHaveLength(0)
      expect(typeof cleanup).toBe('function')

      consoleWarnSpy.mockRestore()
    })

    it('should cleanup poll when cleanup function is called', async () => {
      const callback = vi.fn()

      const cleanup = coordinator.register({
        key: 'test-poll',
        callback,
        interval: 1000,
      })

      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      cleanup()

      // Should not execute after cleanup
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(1)
      expect(coordinator.getRegisteredPolls()).not.toContain('test-poll')
    })
  })

  describe('pause and resume', () => {
    it('should pause a poll', async () => {
      const callback = vi.fn()

      coordinator.register({ key: 'test-poll', callback, interval: 1000 })

      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      coordinator.pause('test-poll')

      // Should not execute after pause
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(1)
    })

    it('should resume a paused poll', async () => {
      const callback = vi.fn()

      coordinator.register({ key: 'test-poll', callback, interval: 1000 })

      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(1)

      coordinator.pause('test-poll')
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(1)

      coordinator.resume('test-poll')

      // Should execute immediately on resume (no delay)
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).toHaveBeenCalledTimes(2)

      // Then continue at interval
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback).toHaveBeenCalledTimes(3)
    })

    it('should resume with jitter when specified', async () => {
      const callback = vi.fn()

      coordinator.register({ key: 'test-poll', callback, interval: 1000 })
      coordinator.pause('test-poll')

      // Mock Math.random for predictable jitter
      const originalRandom = Math.random
      Math.random = () => 0.5 // 50% of 5000ms = 2500ms

      coordinator.resume('test-poll', true)

      // Should not execute immediately
      await vi.advanceTimersByTimeAsync(0)
      expect(callback).not.toHaveBeenCalled()

      // Should execute after jitter delay
      await vi.advanceTimersByTimeAsync(2500)
      expect(callback).toHaveBeenCalledTimes(1)

      Math.random = originalRandom
    })

    it('should handle pause of non-existent poll gracefully', () => {
      expect(() => coordinator.pause('non-existent')).not.toThrow()
    })

    it('should handle resume of non-existent poll gracefully', () => {
      expect(() => coordinator.resume('non-existent')).not.toThrow()
    })

    it('should track poll pause status', async () => {
      const callback = vi.fn()

      coordinator.register({ key: 'test-poll', callback, interval: 1000 })

      await vi.advanceTimersByTimeAsync(0)

      let status = coordinator.getPollStatus('test-poll')
      expect(status?.isPaused).toBe(false)
      expect(status?.lastRun).toBeInstanceOf(Date)

      coordinator.pause('test-poll')

      status = coordinator.getPollStatus('test-poll')
      expect(status?.isPaused).toBe(true)
    })
  })

  describe('pauseAll and resumeAll', () => {
    it('should pause all polls', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 1000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 1000 })

      // Wait for both polls to execute initially (0ms and 1000ms stagger)
      await vi.advanceTimersByTimeAsync(1000)

      const calls1 = callback1.mock.calls.length
      const calls2 = callback2.mock.calls.length

      coordinator.pauseAll()

      // Advance time significantly
      await vi.advanceTimersByTimeAsync(10000)

      // Should not execute additional times after pauseAll
      expect(callback1).toHaveBeenCalledTimes(calls1)
      expect(callback2).toHaveBeenCalledTimes(calls2)
    })

    it('should resume all polls', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 1000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 1000 })

      await vi.advanceTimersByTimeAsync(0)
      coordinator.pauseAll()

      coordinator.resumeAll()

      await vi.advanceTimersByTimeAsync(0)
      expect(callback1).toHaveBeenCalledTimes(2)
      expect(callback2).toHaveBeenCalledTimes(1)
    })

    it('should resume all polls with jitter', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 1000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 1000 })

      coordinator.pauseAll()

      const originalRandom = Math.random
      Math.random = () => 0.5 // 50% of 5000ms = 2500ms

      coordinator.resumeAll(true)

      // Should not execute immediately
      await vi.advanceTimersByTimeAsync(0)
      expect(callback1).not.toHaveBeenCalled()
      expect(callback2).not.toHaveBeenCalled()

      // Should execute after jitter
      await vi.advanceTimersByTimeAsync(2500)
      expect(callback1).toHaveBeenCalled()
      expect(callback2).toHaveBeenCalled()

      Math.random = originalRandom
    })
  })

  describe('auth-aware polling', () => {
    it('should pause authenticated polls', async () => {
      const authCallback = vi.fn()
      const publicCallback = vi.fn()

      coordinator.register({
        key: 'auth-poll',
        callback: authCallback,
        interval: 10000,
        requiresAuth: true,
      })
      coordinator.register({
        key: 'public-poll',
        callback: publicCallback,
        interval: 10000,
        requiresAuth: false,
      })

      // Wait for both polls to execute initially (0ms and 1000ms stagger)
      await vi.advanceTimersByTimeAsync(1000)
      expect(authCallback).toHaveBeenCalledTimes(1)
      expect(publicCallback).toHaveBeenCalledTimes(1)

      coordinator.pauseAuthenticatedPolls()

      // Advance by poll interval
      await vi.advanceTimersByTimeAsync(10000)

      // Auth poll should not continue
      expect(authCallback).toHaveBeenCalledTimes(1)
      // Public poll should continue
      expect(publicCallback).toHaveBeenCalledTimes(2)
    })

    it('should resume authenticated polls', async () => {
      const authCallback = vi.fn()

      coordinator.register({
        key: 'auth-poll',
        callback: authCallback,
        interval: 1000,
        requiresAuth: true,
      })

      await vi.advanceTimersByTimeAsync(0)
      coordinator.pauseAuthenticatedPolls()

      coordinator.resumeAuthenticatedPolls()

      await vi.advanceTimersByTimeAsync(0)
      expect(authCallback).toHaveBeenCalledTimes(2)
    })
  })

  describe('health-aware polling', () => {
    it('should pause health-aware polls by default', async () => {
      const healthAwareCallback = vi.fn()
      const alwaysOnCallback = vi.fn()

      coordinator.register({
        key: 'health-aware',
        callback: healthAwareCallback,
        interval: 10000,
        pauseWhenBackendDown: true,
      })
      coordinator.register({
        key: 'always-on',
        callback: alwaysOnCallback,
        interval: 10000,
        pauseWhenBackendDown: false,
      })

      // Wait for both polls to execute initially (0ms and 1000ms stagger)
      await vi.advanceTimersByTimeAsync(1000)
      expect(healthAwareCallback).toHaveBeenCalledTimes(1)
      expect(alwaysOnCallback).toHaveBeenCalledTimes(1)

      coordinator.pauseHealthAwarePolls()

      // Advance by poll interval
      await vi.advanceTimersByTimeAsync(10000)

      // Health-aware poll should not continue
      expect(healthAwareCallback).toHaveBeenCalledTimes(1)
      // Always-on poll should continue
      expect(alwaysOnCallback).toHaveBeenCalledTimes(2)
    })

    it('should resume health-aware polls with jitter', async () => {
      const callback = vi.fn()

      coordinator.register({
        key: 'health-aware',
        callback,
        interval: 1000,
        pauseWhenBackendDown: true,
      })

      coordinator.pauseHealthAwarePolls()

      const originalRandom = Math.random
      Math.random = () => 0.5

      coordinator.resumeHealthAwarePolls(true)

      await vi.advanceTimersByTimeAsync(2500)
      expect(callback).toHaveBeenCalled()

      Math.random = originalRandom
    })
  })

  describe('window focus handling', () => {
    it('should set up window focus listener', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener')

      coordinator.setupWindowFocusListener()

      expect(addEventListenerSpy).toHaveBeenCalledWith('focus', expect.any(Function))

      addEventListenerSpy.mockRestore()
    })

    it('should warn if focus listener already set up', () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      coordinator.setupWindowFocusListener()
      coordinator.setupWindowFocusListener()

      expect(consoleWarnSpy).toHaveBeenCalled()

      consoleWarnSpy.mockRestore()
    })

    it('should refresh all non-paused polls with stagger on window focus', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()
      const callback3 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 10000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 10000 })
      coordinator.register({ key: 'poll-3', callback: callback3, interval: 10000 })

      // Wait for all polls to execute initially (0ms, 1000ms, 2000ms stagger)
      await vi.advanceTimersByTimeAsync(2000)
      expect(callback1).toHaveBeenCalledTimes(1)
      expect(callback2).toHaveBeenCalledTimes(1)
      expect(callback3).toHaveBeenCalledTimes(1)

      coordinator.setupWindowFocusListener()

      // Pause one poll
      coordinator.pause('poll-2')

      // Trigger focus event
      window.dispatchEvent(new Event('focus'))

      // Poll 1 should execute immediately
      await vi.advanceTimersByTimeAsync(0)
      expect(callback1).toHaveBeenCalledTimes(2) // Initial + focus

      // Poll 2 should not execute (paused)
      expect(callback2).toHaveBeenCalledTimes(1) // Only initial

      // Poll 3 should execute after 1s stagger
      await vi.advanceTimersByTimeAsync(1000)
      expect(callback3).toHaveBeenCalledTimes(2) // Initial + focus
    })

    it('should clean up window focus listener', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      coordinator.setupWindowFocusListener()
      coordinator.cleanupWindowFocusListener()

      expect(removeEventListenerSpy).toHaveBeenCalledWith('focus', expect.any(Function))

      removeEventListenerSpy.mockRestore()
    })
  })

  describe('getPollStatus', () => {
    it('should return poll status', async () => {
      const callback = vi.fn()

      coordinator.register({ key: 'test-poll', callback, interval: 1000 })

      await vi.advanceTimersByTimeAsync(0)

      const status = coordinator.getPollStatus('test-poll')

      expect(status).toEqual({
        isPaused: false,
        lastRun: expect.any(Date),
      })
    })

    it('should return null for non-existent poll', () => {
      const status = coordinator.getPollStatus('non-existent')
      expect(status).toBeNull()
    })
  })

  describe('getRegisteredPolls', () => {
    it('should return all registered poll keys', () => {
      coordinator.register({ key: 'poll-1', callback: vi.fn(), interval: 1000 })
      coordinator.register({ key: 'poll-2', callback: vi.fn(), interval: 1000 })
      coordinator.register({ key: 'poll-3', callback: vi.fn(), interval: 1000 })

      const polls = coordinator.getRegisteredPolls()

      expect(polls).toHaveLength(3)
      expect(polls).toContain('poll-1')
      expect(polls).toContain('poll-2')
      expect(polls).toContain('poll-3')
    })

    it('should return empty array when no polls registered', () => {
      const polls = coordinator.getRegisteredPolls()
      expect(polls).toEqual([])
    })
  })

  describe('dispose', () => {
    it('should clean up all polls', async () => {
      const callback1 = vi.fn()
      const callback2 = vi.fn()

      coordinator.register({ key: 'poll-1', callback: callback1, interval: 1000 })
      coordinator.register({ key: 'poll-2', callback: callback2, interval: 1000 })

      // Wait for both polls to execute initially (0ms and 1000ms stagger)
      await vi.advanceTimersByTimeAsync(1000)

      const calls1 = callback1.mock.calls.length
      const calls2 = callback2.mock.calls.length

      coordinator.dispose()

      // Should not execute after disposal
      await vi.advanceTimersByTimeAsync(10000)

      expect(callback1).toHaveBeenCalledTimes(calls1)
      expect(callback2).toHaveBeenCalledTimes(calls2)
      expect(coordinator.getRegisteredPolls()).toEqual([])
    })

    it('should clean up focus listener on dispose', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      coordinator.setupWindowFocusListener()
      coordinator.dispose()

      expect(removeEventListenerSpy).toHaveBeenCalledWith('focus', expect.any(Function))

      removeEventListenerSpy.mockRestore()
    })

    it('should handle multiple dispose calls gracefully', () => {
      expect(() => {
        coordinator.dispose()
        coordinator.dispose()
      }).not.toThrow()
    })
  })
})
