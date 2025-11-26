/**
 * Configuration types and validation for the TfL Alerts frontend.
 *
 * Configuration is loaded from /config.json at runtime by ConfigLoader component.
 * This module provides TypeScript types and validation logic only.
 *
 * NO FALLBACK VALUES - Missing configuration will throw an error to make
 * misconfigurations immediately visible.
 *
 * @see configLoader.ts - Runtime config loading
 * @see ConfigContext.tsx - React Context provider for config access
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
export function validateConfig(config: Partial<AppConfig>): asserts config is AppConfig {
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
