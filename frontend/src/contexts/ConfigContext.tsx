/**
 * Configuration Context - provides runtime config to all components
 *
 * Config is loaded once at app startup and made available via useConfig() hook.
 * Components can access config without prop drilling.
 */

import { createContext, useContext } from 'react'
import type { AppConfig } from '../lib/config'

/**
 * Context for application configuration
 */
const ConfigContext = createContext<AppConfig | undefined>(undefined)

/**
 * Props for ConfigProvider component
 */
interface ConfigProviderProps {
  config: AppConfig
  children: React.ReactNode
}

/**
 * Provider component that makes config available to all children
 *
 * @param props.config - Validated configuration object
 * @param props.children - Child components
 */
export function ConfigProvider({ config, children }: ConfigProviderProps) {
  return <ConfigContext.Provider value={config}>{children}</ConfigContext.Provider>
}

/**
 * Hook to access configuration in any component
 *
 * @throws {Error} If used outside ConfigProvider
 * @returns AppConfig - Application configuration
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const config = useConfig()
 *   return <div>API: {config.api.baseUrl}</div>
 * }
 * ```
 */
export function useConfig(): AppConfig {
  const config = useContext(ConfigContext)

  if (config === undefined) {
    throw new Error('useConfig must be used within ConfigProvider')
  }

  return config
}
