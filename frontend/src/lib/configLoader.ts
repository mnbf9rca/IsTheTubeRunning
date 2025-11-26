/**
 * Configuration loader - fetches and validates config at runtime
 *
 * This module loads configuration from /config.json at application startup.
 * The config.json contains all environments (development, production, test).
 * Environment is auto-detected based on window.location.hostname:
 *   - localhost or 127.0.0.1 → development
 *   - isthetube.cynexia.com → production
 *
 * This allows the same Docker image to be used across different environments
 * with ZERO configuration - just works based on hostname.
 */

import type { AppConfig } from './config'
import { validateConfig } from './config'

type Environment = 'development' | 'production'

interface MultiEnvConfig {
  development: AppConfig
  production: AppConfig
}

/**
 * Detect current environment based on hostname
 *
 * @returns Environment name ('development' or 'production')
 */
function detectEnvironment(): Environment {
  const hostname = window.location.hostname

  // Development: localhost, 127.0.0.1, or any local hostname
  if (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.startsWith('192.168.') ||
    hostname.startsWith('10.') ||
    hostname.endsWith('.local')
  ) {
    return 'development'
  }

  // Production: everything else (specifically isthetube.cynexia.com)
  return 'production'
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
