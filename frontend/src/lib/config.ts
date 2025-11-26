/**
 * Centralized configuration module for the TfL Alerts frontend.
 *
 * Configuration is loaded from JSON files in /config directory based on the current
 * environment (development, production, test). All values are validated at startup
 * to ensure no misconfigurations reach runtime.
 *
 * NO FALLBACK VALUES - Missing configuration will throw an error to make
 * misconfigurations immediately visible.
 */

/**
 * Configuration structure for the application
 */
export interface AppConfig {
  api: {
    baseUrl: string
  }
  auth0: {
    domain: string
    clientId: string
    audience: string
    callbackUrl: string
  }
}

/**
 * Basic URL validation
 */
function isValidUrl(url: string): boolean {
  try {
    new URL(url)
    return true
  } catch {
    return false
  }
}

/**
 * Validates that all required configuration values are present
 *
 * @throws {Error} If any required configuration value is missing or invalid
 */
function validateConfig(config: Partial<AppConfig>): asserts config is AppConfig {
  const errors: string[] = []

  // Validate API config
  if (!config.api?.baseUrl) {
    errors.push('api.baseUrl is required')
  } else if (!isValidUrl(config.api.baseUrl)) {
    errors.push(`api.baseUrl must be a valid URL, got: ${config.api.baseUrl}`)
  }

  // Validate Auth0 config
  if (!config.auth0?.domain) {
    errors.push('auth0.domain is required')
  }
  if (!config.auth0?.clientId) {
    errors.push('auth0.clientId is required')
  }
  if (!config.auth0?.audience) {
    errors.push('auth0.audience is required')
  }
  if (!config.auth0?.callbackUrl) {
    errors.push('auth0.callbackUrl is required')
  } else if (!isValidUrl(config.auth0.callbackUrl)) {
    errors.push(`auth0.callbackUrl must be a valid URL, got: ${config.auth0.callbackUrl}`)
  }

  if (errors.length > 0) {
    throw new Error(`Configuration validation failed:\n${errors.map((e) => `  - ${e}`).join('\n')}`)
  }
}

/**
 * Load configuration at module initialization using top-level await
 * Vite replaces import.meta.env.MODE with a string literal (e.g., 'production'),
 * allowing tree-shaking to eliminate unused config files from the bundle
 */
let configData: Partial<AppConfig>

if (import.meta.env.MODE === 'production') {
  const mod = await import('../../config/config.production.json')
  configData = mod.default
} else if (import.meta.env.MODE === 'test') {
  const mod = await import('../../config/config.test.json')
  configData = mod.default
} else {
  const mod = await import('../../config/config.development.json')
  configData = mod.default
}

// Validate the loaded configuration
validateConfig(configData)

/**
 * Application configuration - loaded at module initialization
 */
export const config: AppConfig = configData

/**
 * Get the application configuration
 */
export function getConfig(): AppConfig {
  return config
}
