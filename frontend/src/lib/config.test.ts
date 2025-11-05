import { describe, it, expect, vi } from 'vitest'

// Mock the JSON imports before importing config module
vi.mock('../../config/config.development.json', () => ({
  default: {
    api: { baseUrl: 'http://localhost:8000' },
    auth0: {
      domain: 'test.auth0.com',
      clientId: 'test-client-id',
      audience: 'https://api.test.com',
      callbackUrl: 'http://localhost:5173/callback',
    },
  },
}))

vi.mock('../../config/config.production.json', () => ({
  default: {
    api: { baseUrl: 'https://api.prod.com' },
    auth0: {
      domain: 'prod.auth0.com',
      clientId: 'prod-client-id',
      audience: 'https://api.prod.com',
      callbackUrl: 'https://prod.com/callback',
    },
  },
}))

vi.mock('../../config/config.test.json', () => ({
  default: {
    api: { baseUrl: 'http://test:8000' },
    auth0: {
      domain: 'test.auth0.com',
      clientId: 'test-client-id',
      audience: 'https://api.test.com',
      callbackUrl: 'http://test/callback',
    },
  },
}))

describe('config', () => {
  it('should load valid configuration successfully', async () => {
    const { config } = await import('./config')

    expect(config).toBeDefined()
    expect(config.api.baseUrl).toBeDefined()
    expect(config.auth0.domain).toBeDefined()
    expect(config.auth0.clientId).toBeDefined()
    expect(config.auth0.audience).toBeDefined()
    expect(config.auth0.callbackUrl).toBeDefined()
  })

  it('should have valid API base URL', async () => {
    const { config } = await import('./config')

    // Should be a valid URL
    expect(() => new URL(config.api.baseUrl)).not.toThrow()
  })

  it('should have valid Auth0 callback URL', async () => {
    const { config } = await import('./config')

    // Should be a valid URL
    expect(() => new URL(config.auth0.callbackUrl)).not.toThrow()
  })

  it('should have all required Auth0 fields populated', async () => {
    const { config } = await import('./config')

    expect(config.auth0.domain).toBeTruthy()
    expect(config.auth0.domain).toMatch(/\w+/)
    expect(config.auth0.clientId).toBeTruthy()
    expect(config.auth0.clientId).toMatch(/\w+/)
    expect(config.auth0.audience).toBeTruthy()
    expect(config.auth0.callbackUrl).toBeTruthy()
  })

  it('should have API config with baseUrl', async () => {
    const { config } = await import('./config')

    expect(config.api).toBeDefined()
    expect(config.api.baseUrl).toBeDefined()
    expect(typeof config.api.baseUrl).toBe('string')
  })

  it('should have Auth0 config with all fields', async () => {
    const { config } = await import('./config')

    expect(config.auth0).toBeDefined()
    expect(config.auth0.domain).toBeDefined()
    expect(config.auth0.clientId).toBeDefined()
    expect(config.auth0.audience).toBeDefined()
    expect(config.auth0.callbackUrl).toBeDefined()
  })

  it('should export AppConfig interface type', async () => {
    // TypeScript compile-time check - this test verifies the export exists
    const module = await import('./config')

    expect(module.config).toBeDefined()
    // Type checking happens at compile time
  })
})
