/**
 * ConfigLoader - Loads and validates configuration before rendering app
 *
 * Fetches /config.json on mount, validates it, and provides it to children
 * via ConfigContext. Shows loading/error states during fetch.
 */

import { useEffect, useState } from 'react'
import { ConfigProvider } from '../contexts/ConfigContext'
import { loadConfig } from '../lib/configLoader'
import { setApiBaseUrl } from '../lib/api'
import type { AppConfig } from '../lib/config'

interface ConfigLoaderProps {
  children: React.ReactNode
}

/**
 * Loading state component
 */
function LoadingState() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <div
          className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-current border-r-transparent motion-reduce:animate-[spin_1.5s_linear_infinite]"
          role="status"
        >
          <span className="sr-only">Loading configuration...</span>
        </div>
        <p className="text-gray-600">Loading configuration...</p>
      </div>
    </div>
  )
}

/**
 * Error state component
 */
function ErrorState({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="max-w-md rounded-lg bg-white p-6 shadow-lg">
        <h1 className="mb-4 text-2xl font-bold text-red-600">Configuration Error</h1>
        <p className="mb-4 text-gray-700">Failed to load application configuration:</p>
        <pre className="mb-4 overflow-auto rounded bg-gray-100 p-4 text-sm text-gray-800">
          {error}
        </pre>
        <p className="mb-4 text-sm text-gray-600">
          This usually means the config.json file is missing, invalid, or the server is unreachable.
        </p>
        <button
          onClick={onRetry}
          className="w-full rounded bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        >
          Retry
        </button>
      </div>
    </div>
  )
}

/**
 * ConfigLoader component - Loads config and provides it to children
 *
 * @param props.children - App components to render after config loads
 */
export function ConfigLoader({ children }: ConfigLoaderProps) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchConfig = async () => {
    setLoading(true)
    setError(null)

    try {
      const loadedConfig = await loadConfig()
      // Set API base URL for api.ts module
      setApiBaseUrl(loadedConfig.api.baseUrl)
      setConfig(loadedConfig)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchConfig()
  }, [])

  if (loading) {
    return <LoadingState />
  }

  if (error) {
    return <ErrorState error={error} onRetry={fetchConfig} />
  }

  if (!config) {
    return <ErrorState error="Configuration is null after loading" onRetry={fetchConfig} />
  }

  return <ConfigProvider config={config}>{children}</ConfigProvider>
}
