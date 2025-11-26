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

import * as ipaddr from 'ipaddr.js'
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
 * Uses explicit production domain matching and ipaddr.js for robust
 * IP address validation (including IPv4/IPv6 private ranges).
 *
 * @returns Environment name ('development' or 'production')
 */
function detectEnvironment(): Environment {
  const hostname = window.location.hostname

  // Production: explicit production domain
  if (hostname === 'isthetube.cynexia.com') {
    console.log('[ConfigLoader] Detected production environment (explicit domain match)')
    return 'production'
  }

  // Development: localhost keyword
  if (hostname === 'localhost' || hostname.endsWith('.local')) {
    console.log('[ConfigLoader] Detected development environment (localhost)')
    return 'development'
  }

  // Development: private IP addresses (RFC 1918 for IPv4, ULA/link-local for IPv6)
  try {
    const addr = ipaddr.process(hostname)
    const range = addr.range()

    if (
      range === 'private' ||
      range === 'loopback' ||
      range === 'uniqueLocal' ||
      range === 'linkLocal'
    ) {
      console.log(`[ConfigLoader] Detected development environment (${range} IP: ${hostname})`)
      return 'development'
    }
  } catch {
    // Not a valid IP address, treat as domain name
  }

  // Unknown hostname - default to production with warning
  console.warn(`[ConfigLoader] Unknown hostname: ${hostname}, defaulting to production`)
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
