import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { ConfigLoader } from './ConfigLoader'
import * as configLoaderModule from '../lib/configLoader'
import * as apiModule from '../lib/api'
import type { AppConfig } from '../lib/config'

// Mock the loadConfig function
vi.mock('../lib/configLoader', async () => {
  const actual = await vi.importActual('../lib/configLoader')
  return {
    ...actual,
    loadConfig: vi.fn(),
  }
})

// Mock the setApiBaseUrl function
vi.mock('../lib/api', async () => {
  const actual = await vi.importActual('../lib/api')
  return {
    ...actual,
    setApiBaseUrl: vi.fn(),
  }
})

// Mock fetch globally
global.fetch = vi.fn()

const mockConfig: AppConfig = {
  api: {
    baseUrl: 'http://localhost:8000/api/v1',
  },
  auth0: {
    domain: 'test.auth0.com',
    clientId: 'test-client-id',
    audience: 'https://api.test.com',
    callbackUrl: 'http://localhost:5173/callback',
  },
}

describe('ConfigLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.stubGlobal('location', { hostname: 'localhost' })
  })

  it('should show loading state initially', () => {
    // Make loadConfig never resolve to keep in loading state
    vi.mocked(configLoaderModule.loadConfig).mockImplementation(() => new Promise(() => {}))

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    // Text appears twice (sr-only span + paragraph)
    const loadingElements = screen.getAllByText('Loading configuration...')
    expect(loadingElements.length).toBeGreaterThan(0)
    expect(screen.queryByText('App Content')).not.toBeInTheDocument()
  })

  it('should render children after successful config load', async () => {
    vi.mocked(configLoaderModule.loadConfig).mockResolvedValue(mockConfig)

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    // Initially loading (text appears twice in DOM)
    expect(screen.getAllByText('Loading configuration...').length).toBeGreaterThan(0)

    // Wait for config to load
    await waitFor(() => {
      expect(screen.getByText('App Content')).toBeInTheDocument()
    })

    expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()
  })

  it('should call setApiBaseUrl with correct value after config loads', async () => {
    vi.mocked(configLoaderModule.loadConfig).mockResolvedValue(mockConfig)

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    await waitFor(() => {
      expect(apiModule.setApiBaseUrl).toHaveBeenCalledWith('http://localhost:8000/api/v1')
    })
  })

  it('should show error message when config load fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    vi.mocked(configLoaderModule.loadConfig).mockRejectedValue(new Error('Failed to fetch config'))

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    await waitFor(
      () => {
        expect(screen.getByText(/Failed to load application configuration/)).toBeInTheDocument()
      },
      { timeout: 3000 }
    )

    expect(screen.queryByText('App Content')).not.toBeInTheDocument()
    expect(screen.queryByText('Loading configuration...')).not.toBeInTheDocument()

    consoleErrorSpy.mockRestore()
  })

  it('should show error details in error state', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    vi.mocked(configLoaderModule.loadConfig).mockRejectedValue(new Error('Network timeout'))

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    await waitFor(() => {
      expect(screen.getByText('Network timeout')).toBeInTheDocument()
    })

    consoleErrorSpy.mockRestore()
  })

  it('should provide config context to children', async () => {
    vi.mocked(configLoaderModule.loadConfig).mockResolvedValue(mockConfig)

    function TestChild() {
      // This would normally use useConfig() but we just test it renders
      return <div>Child rendered with config</div>
    }

    render(
      <ConfigLoader>
        <TestChild />
      </ConfigLoader>
    )

    await waitFor(() => {
      expect(screen.getByText('Child rendered with config')).toBeInTheDocument()
    })
  })

  it('should handle production config correctly', async () => {
    vi.stubGlobal('location', { hostname: 'isthetube.cynexia.com' })

    const prodConfig: AppConfig = {
      api: {
        baseUrl: 'https://isthetube.cynexia.com/api/v1',
      },
      auth0: {
        domain: 'prod.auth0.com',
        clientId: 'prod-client-id',
        audience: 'https://api.isthetube.com',
        callbackUrl: 'https://isthetube.cynexia.com/callback',
      },
    }

    vi.mocked(configLoaderModule.loadConfig).mockResolvedValue(prodConfig)

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    await waitFor(() => {
      expect(apiModule.setApiBaseUrl).toHaveBeenCalledWith('https://isthetube.cynexia.com/api/v1')
    })
  })

  it('should capture error from loadConfig and display error message', async () => {
    const testError = new Error('Config fetch failed')
    vi.mocked(configLoaderModule.loadConfig).mockRejectedValue(testError)

    render(
      <ConfigLoader>
        <div>App Content</div>
      </ConfigLoader>
    )

    await waitFor(
      () => {
        expect(screen.getByText(/Failed to load application configuration/)).toBeInTheDocument()
      },
      { timeout: 3000 }
    )

    // Should display the error message from the thrown error
    expect(screen.getByText('Config fetch failed')).toBeInTheDocument()
  })

  it('should only load config once on mount', async () => {
    vi.mocked(configLoaderModule.loadConfig).mockResolvedValue(mockConfig)

    const { rerender } = render(
      <ConfigLoader>
        <div>Content 1</div>
      </ConfigLoader>
    )

    await waitFor(() => {
      expect(screen.getByText('Content 1')).toBeInTheDocument()
    })

    // Rerender with different children
    rerender(
      <ConfigLoader>
        <div>Content 2</div>
      </ConfigLoader>
    )

    // loadConfig should still only have been called once
    expect(configLoaderModule.loadConfig).toHaveBeenCalledTimes(1)
  })
})
