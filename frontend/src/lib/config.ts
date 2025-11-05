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
 * Import all config files eagerly
 * Vite will bundle these at build time
 */
import configDevelopment from '../../config/config.development.json'
import configProduction from '../../config/config.production.json'
import configTest from '../../config/config.test.json'

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
 * Gets the current environment mode
 */
function getEnvironment(): 'development' | 'production' | 'test' {
  // In Vite, import.meta.env.MODE is set based on the --mode flag or NODE_ENV
  const mode = import.meta.env.MODE

  if (mode === 'test') return 'test'
  if (mode === 'production') return 'production'
  return 'development'
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
 * Loads configuration from the appropriate JSON file based on environment
 *
 * @throws {Error} If configuration file cannot be loaded or validation fails
 */
function loadConfig(): AppConfig {
  const env = getEnvironment()

  // Select the appropriate config based on environment
  let configData: Partial<AppConfig>

  switch (env) {
    case 'development':
      configData = configDevelopment
      break
    case 'production':
      configData = configProduction
      break
    case 'test':
      configData = configTest
      break
    default:
      throw new Error(`Unknown environment: ${env}`)
  }

  // Validate the loaded configuration
  validateConfig(configData)

  return configData
}

/**
 * Application configuration singleton
 *
 * Loaded once at module initialization. Any configuration errors will be thrown
 * immediately when this module is first imported, ensuring the app cannot start
 * with invalid configuration.
 */
export const config: AppConfig = loadConfig()
