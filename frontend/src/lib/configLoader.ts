/**
 * Configuration loader - fetches and validates config at runtime
 *
 * This module loads configuration from /config.json at application startup.
 * The config.json contains all environments (development, production).
 * Environment is auto-detected based on window.location.hostname:
 *   - isthetube.cynexia.com → production
 *   - All other hostnames → development (safer default)
 *
 * This allows the same Docker image to be used across different environments
 * with ZERO configuration - just works based on hostname.
 */

import type { AppConfig } from './config'
import { validateConfig } from './config'

type Environment = 'development' | 'production'

export interface MultiEnvConfig {
  development: AppConfig
  production: AppConfig
}

/**
 * Detect current environment based on hostname
 *
 * Simple explicit matching - production domain only.
 * All other hostnames (localhost, IPs, staging, unknown) default to development.
 * This is the safer default - prevents accidental production API usage.
 *
 * @returns Environment name ('development' or 'production')
 */
function detectEnvironment(): Environment {
  const { hostname } = window.location

  // Production: explicit production domain only
  if (hostname === 'isthetube.cynexia.com') {
    console.log('[ConfigLoader] Detected production environment:', hostname)
    return 'production'
  }

  // Everything else is development (localhost, IPs, staging, unknown)
  console.log('[ConfigLoader] Detected development environment:', hostname)
  return 'development'
}

/**
 * Fetch and validate application configuration from /config.json
 *
 * @throws {Error} If config fetch fails or validation fails
 * @returns Promise<AppConfig> Validated configuration object for current environment
 */
export async function loadConfig(): Promise<AppConfig> {
  try {
    const response = await fetch('/config.json')

    if (!response.ok) {
      throw new Error(`Failed to fetch config: ${response.status} ${response.statusText}`)
    }

    const multiEnvConfig = (await response.json()) as MultiEnvConfig

    // Detect which environment we're in
    const environment = detectEnvironment()
    console.log(`[ConfigLoader] Detected environment: ${environment}`)

    // Extract config for current environment
    const configData = multiEnvConfig[environment]

    if (!configData) {
      throw new Error(`Configuration for environment "${environment}" not found in config.json`)
    }

    // This will throw if validation fails
    validateConfig(configData)

    console.log(`[ConfigLoader] Loaded config for ${environment}:`, {
      apiBaseUrl: configData.api.baseUrl,
      auth0Domain: configData.auth0.domain,
    })

    return configData as AppConfig
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Configuration loading failed: ${error.message}`)
    }
    throw new Error('Configuration loading failed: Unknown error')
  }
}
