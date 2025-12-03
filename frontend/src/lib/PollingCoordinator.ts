/**
 * PollingCoordinator - Centralized polling management with staggering and coordination
 *
 * Features:
 * - Staggered poll start times (prevents simultaneous API calls)
 * - Auth-aware polling (pause authenticated polls when logged out)
 * - Health-aware polling (pause all polls when backend unavailable)
 * - Recovery jitter (random delay on backend recovery to prevent thundering herd)
 * - Consolidated window focus handling
 */

export interface PollingOptions {
  /** Unique key to identify this poll */
  key: string
  /** Callback function to execute on each poll interval */
  callback: () => void | Promise<void>
  /** Poll interval in milliseconds */
  interval: number
  /** Whether this poll requires authentication (default: false) */
  requiresAuth?: boolean
  /** Whether to pause when backend is unavailable (default: true) */
  pauseWhenBackendDown?: boolean
}

interface PollingEntry {
  options: PollingOptions
  timerId: ReturnType<typeof setTimeout> | null
  isPaused: boolean
  lastRun: Date | null
}

export class PollingCoordinator {
  private polls: Map<string, PollingEntry> = new Map()
  private staggerIndex = 0
  private readonly MAX_STAGGER_MS = 5000
  private readonly STAGGER_INCREMENT_MS = 1000
  private focusListener: (() => void) | null = null
  private isDisposed = false

  /**
   * Register a new poll with the coordinator
   * @param options Polling configuration
   * @returns Cleanup function to unregister the poll
   */
  register(options: PollingOptions): () => void {
    if (this.isDisposed) {
      console.warn(
        `[PollingCoordinator] Attempted to register poll "${options.key}" after disposal`
      )
      return () => {}
    }

    if (this.polls.has(options.key)) {
      console.warn(`[PollingCoordinator] Poll "${options.key}" already registered, replacing`)
      this.unregister(options.key)
    }

    // Calculate stagger delay for this poll
    const staggerDelay = (this.staggerIndex * this.STAGGER_INCREMENT_MS) % this.MAX_STAGGER_MS
    this.staggerIndex++

    // Create poll entry
    const entry: PollingEntry = {
      options,
      timerId: null,
      isPaused: false,
      lastRun: null,
    }

    this.polls.set(options.key, entry)

    // Start polling with stagger delay
    this.startPoll(options.key, staggerDelay)

    // Return cleanup function
    return () => this.unregister(options.key)
  }

  /**
   * Unregister a poll
   */
  private unregister(key: string): void {
    const entry = this.polls.get(key)
    if (entry) {
      if (entry.timerId !== null) {
        clearTimeout(entry.timerId)
      }
      this.polls.delete(key)
    }
  }

  /**
   * Start polling for a given key with optional initial delay
   */
  private startPoll(key: string, initialDelay = 0): void {
    const entry = this.polls.get(key)
    if (!entry || entry.isPaused) return

    const executeCallback = async () => {
      const currentEntry = this.polls.get(key)
      if (!currentEntry || currentEntry.isPaused) return

      try {
        await currentEntry.options.callback()
        currentEntry.lastRun = new Date()
      } catch (error) {
        console.error(`[PollingCoordinator] Poll "${key}" callback failed:`, error)
      }

      // Schedule next execution
      this.scheduleNext(key)
    }

    // Schedule with initial delay
    entry.timerId = setTimeout(executeCallback, initialDelay)
  }

  /**
   * Schedule the next poll execution
   */
  private scheduleNext(key: string): void {
    const entry = this.polls.get(key)
    if (!entry || entry.isPaused) return

    entry.timerId = setTimeout(async () => {
      const currentEntry = this.polls.get(key)
      if (!currentEntry || currentEntry.isPaused) return

      try {
        await currentEntry.options.callback()
        currentEntry.lastRun = new Date()
      } catch (error) {
        console.error(`[PollingCoordinator] Poll "${key}" callback failed:`, error)
      }

      // Continue polling
      this.scheduleNext(key)
    }, entry.options.interval)
  }

  /**
   * Pause a specific poll
   */
  pause(key: string): void {
    const entry = this.polls.get(key)
    if (entry && !entry.isPaused) {
      entry.isPaused = true
      if (entry.timerId !== null) {
        clearTimeout(entry.timerId)
        entry.timerId = null
      }
    }
  }

  /**
   * Resume a specific poll
   */
  resume(key: string, withJitter = false): void {
    const entry = this.polls.get(key)
    if (entry && entry.isPaused) {
      entry.isPaused = false
      const jitterDelay = withJitter ? Math.random() * 5000 : 0
      this.startPoll(key, jitterDelay)
    }
  }

  /**
   * Pause all polls
   */
  pauseAll(): void {
    for (const [key] of this.polls) {
      this.pause(key)
    }
  }

  /**
   * Resume all polls with optional jitter
   */
  resumeAll(withJitter = false): void {
    for (const [key] of this.polls) {
      this.resume(key, withJitter)
    }
  }

  /**
   * Pause polls that require authentication
   */
  pauseAuthenticatedPolls(): void {
    for (const [key, entry] of this.polls) {
      if (entry.options.requiresAuth) {
        this.pause(key)
      }
    }
  }

  /**
   * Resume polls that require authentication
   */
  resumeAuthenticatedPolls(): void {
    for (const [key, entry] of this.polls) {
      if (entry.options.requiresAuth) {
        this.resume(key)
      }
    }
  }

  /**
   * Pause polls that should pause when backend is down
   */
  pauseHealthAwarePolls(): void {
    for (const [key, entry] of this.polls) {
      if (entry.options.pauseWhenBackendDown !== false) {
        this.pause(key)
      }
    }
  }

  /**
   * Resume polls that were paused due to backend health
   */
  resumeHealthAwarePolls(withJitter = false): void {
    for (const [key, entry] of this.polls) {
      if (entry.options.pauseWhenBackendDown !== false) {
        this.resume(key, withJitter)
      }
    }
  }

  /**
   * Set up window focus listener for coordinated refresh
   */
  setupWindowFocusListener(): void {
    if (this.focusListener) {
      console.warn('[PollingCoordinator] Focus listener already set up')
      return
    }

    this.focusListener = () => {
      // Refresh all non-paused polls with stagger
      let stagger = 0
      for (const [key, entry] of this.polls) {
        if (!entry.isPaused) {
          setTimeout(() => {
            // Execute callback immediately (not waiting for next interval)
            Promise.resolve(entry.options.callback()).catch((error: unknown) => {
              console.error(`[PollingCoordinator] Focus refresh for "${key}" failed:`, error)
            })
          }, stagger)
          stagger += this.STAGGER_INCREMENT_MS
        }
      }
    }

    window.addEventListener('focus', this.focusListener)
  }

  /**
   * Clean up window focus listener
   */
  cleanupWindowFocusListener(): void {
    if (this.focusListener) {
      window.removeEventListener('focus', this.focusListener)
      this.focusListener = null
    }
  }

  /**
   * Get poll status (for debugging/testing)
   */
  getPollStatus(key: string): { isPaused: boolean; lastRun: Date | null } | null {
    const entry = this.polls.get(key)
    return entry ? { isPaused: entry.isPaused, lastRun: entry.lastRun } : null
  }

  /**
   * Get all registered poll keys (for debugging/testing)
   */
  getRegisteredPolls(): string[] {
    return Array.from(this.polls.keys())
  }

  /**
   * Dispose the coordinator and clean up all polls
   */
  dispose(): void {
    if (this.isDisposed) return

    this.isDisposed = true

    // Clean up all polls
    for (const [key] of this.polls) {
      this.unregister(key)
    }
    this.polls.clear()

    // Clean up focus listener
    this.cleanupWindowFocusListener()
  }
}
